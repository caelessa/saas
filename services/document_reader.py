import io
import re
import shutil
from pathlib import Path

from pypdf import PdfReader


def _clean(value):
    return re.sub(r"\s+", " ", value or "").strip()


def _normalize(text):
    text = (text or "").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _looks_like_cnh_data(text):
    upper = (text or "").upper()
    useful = ["NOME", "CPF", "NASCIMENTO", "VALIDADE", "REGISTRO", "CATEGORIA", "FILIAÇÃO", "FILIACAO"]
    return sum(term in upper for term in useful) >= 2


def _ocr_image(image, psm=6, timeout=35):
    try:
        import pytesseract
        from PIL import ImageEnhance, ImageFilter, ImageOps

        tesseract_path = shutil.which("tesseract")
        if tesseract_path is None:
            return "[ERRO OCR: executável tesseract não encontrado no servidor]"
        pytesseract.pytesseract.tesseract_cmd = tesseract_path

        image = image.convert("L")
        image = ImageOps.autocontrast(image)
        image = ImageEnhance.Contrast(image).enhance(1.7)
        image = image.filter(ImageFilter.SHARPEN)

        try:
            return pytesseract.image_to_string(
                image,
                lang="por",
                config=f"--oem 3 --psm {psm}",
                timeout=timeout,
            )
        except RuntimeError:
            return f"[ERRO OCR: tempo máximo de {timeout} segundos excedido]"
        except Exception:
            return pytesseract.image_to_string(
                image,
                config=f"--oem 3 --psm {psm}",
                timeout=timeout,
            )
    except Exception as exc:
        return f"[ERRO OCR: {type(exc).__name__}: {exc}]"


def _ocr_pdf(data):
    try:
        import fitz
        from PIL import Image

        document = fitz.open(stream=data, filetype="pdf")
        if len(document) == 0:
            return ""

        page = document[0]
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5), alpha=False)
        image = Image.open(io.BytesIO(pixmap.tobytes("png")))

        width, height = image.size

        # CNH-e padrão: documento na metade esquerda da página.
        # 1) área de dados, excluindo boa parte da foto e do QR Code externo.
        data_crop = image.crop((
            int(width * 0.10),
            int(height * 0.04),
            int(width * 0.53),
            int(height * 0.58),
        ))

        # 2) zona de leitura mecânica (MRZ), excelente para nome e datas.
        mrz_crop = image.crop((
            0,
            int(height * 0.56),
            int(width * 0.53),
            int(height * 0.84),
        ))

        data_text = _normalize(_ocr_image(data_crop, psm=6, timeout=35))
        mrz_text = _normalize(_ocr_image(mrz_crop, psm=6, timeout=25))

        return _normalize(
            "--- DADOS DA CNH ---\n" + data_text +
            "\n\n--- ZONA DE LEITURA MECÂNICA ---\n" + mrz_text
        )
    except Exception as exc:
        return f"[ERRO OCR PDF: {type(exc).__name__}: {exc}]"


def extract_text(file_storage):
    name = (file_storage.filename or "").lower()
    data = file_storage.read()
    file_storage.stream.seek(0)
    digital_text = ""

    if name.endswith(".pdf"):
        try:
            reader = PdfReader(io.BytesIO(data))
            digital_text = "\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception:
            digital_text = ""

        # Não basta o PDF conter texto: ele precisa conter os campos da CNH/CRLV.
        # Documentos Senatran costumam expor apenas o aviso do QR Code na camada textual.
        if not _looks_like_cnh_data(digital_text):
            ocr_text = _ocr_pdf(data)
            if ocr_text:
                return _normalize(digital_text + "\n\n--- OCR DA IMAGEM ---\n" + ocr_text)
        return _normalize(digital_text)

    try:
        from PIL import Image
        return _normalize(_ocr_image(Image.open(io.BytesIO(data))))
    except Exception:
        return ""


def first(patterns, text, flags=re.I):
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            return _clean(match.group(1))
    return ""


def _all_dates(text):
    return re.findall(r"\b\d{2}/\d{2}/\d{4}\b", text or "")



def _parse_cnh_mrz(text):
    """Extrai nome, nascimento e validade da zona de leitura mecânica."""
    lines = []
    for raw in (text or "").upper().splitlines():
        line = re.sub(r"[^A-Z0-9<]", "", raw)
        if len(line) >= 20 and "<" in line:
            lines.append(line)

    result = {"nome": "", "data_nascimento": "", "validade_cnh": ""}

    # Nome: linha com separadores << e predominância de letras.
    name_lines = [
        line for line in lines
        if "<<" in line and sum(ch.isalpha() for ch in line) >= 8
        and not line.startswith("I<BRA")
    ]
    if name_lines:
        line = max(name_lines, key=lambda value: sum(ch.isalpha() for ch in value))
        words = [word for word in re.split(r"<+", line) if len(word) >= 2]
        if 2 <= len(words) <= 7:
            result["nome"] = " ".join(words)

    # Linha 2 no padrão TD1: YYMMDD + dígito + sexo + YYMMDD + dígito.
    for line in lines:
        match = re.search(r"(\d{6})\d?[MF<](\d{6})\d?", line)
        if not match:
            continue

        from datetime import date

        def decode_yymmdd(value, expiry=False):
            yy, mm, dd = int(value[:2]), int(value[2:4]), int(value[4:6])
            current_yy = date.today().year % 100
            if expiry:
                year = 2000 + yy
            else:
                year = 1900 + yy if yy > current_yy else 2000 + yy
            try:
                return f"{dd:02d}/{mm:02d}/{year:04d}"
            except Exception:
                return ""

        result["data_nascimento"] = decode_yymmdd(match.group(1), expiry=False)
        result["validade_cnh"] = decode_yymmdd(match.group(2), expiry=True)
        break

    return result


def parse_cnh(text):
    t = _normalize(text)
    upper = t.upper()

    cpf = first([
        r"CPF\s*[:\-]?\s*([0-9.\-]{11,14})",
        r"\b(\d{3}\.\d{3}\.\d{3}-\d{2})\b",
        r"\b(\d{11})\b",
    ], t)

    registro = first([
        r"(?:N[ºO°]?\s*REGISTRO|REGISTRO)\s*[:\-]?\s*(\d{9,12})",
        r"(?:N[ºO°]?\s*CNH|CNH)\s*[:\-]?\s*(\d{9,12})",
        r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\s+(\d{9,12})\b",
    ], t)

    validade = first([
        r"VALIDADE\s*[:\-]?\s*(\d{1,2}/\d{1,2}/\d{4})",
        r"DATA\s+VALIDADE\s*[:\-]?\s*(\d{1,2}/\d{1,2}/\d{4})",
    ], t)

    nascimento = first([
        r"(?:DATA\s+E?\s*LOCAL\s+E?UF\s+DE\s+NASCIMENTO|DATA\s+DE\s+NASCIMENTO|NASCIMENTO)\s*[:\-]?\s*\n?\s*(\d{1,2}/\d{1,2}/\d{4})",
        r"\b(\d{1,2}/\d{1,2}/\d{4})\s*,?\s*[A-ZÁÀÂÃÉÊÍÓÔÕÚÜÇ ]{3,},\s*[A-Z]{2}\b",
    ], t)

    categoria = first([
        r"\b\d{3}[.]?\d{3}[.]?\d{3}[-]?\d{2}\s+[|Il ]*\d{9,12}\s+([A-E]{1,2})\b",
        r"\b\d{9,12}\s+([A-E]{1,2})\b",
        r"CATEGORIA\s*[:\-]?\s*([A-E]{1,2})\b",
        r"CAT\.?\s*HAB\.?\s*[:\-]?\s*([A-E]{1,2})\b",
    ], t)
    categoria = categoria.upper() if categoria and categoria.upper() in {"A", "B", "C", "D", "E", "AB", "AC", "AD", "AE"} else ""

    # Primeiro tenta a linha imediatamente após o título da CNH.
    nome = first([
        r"CARTEIRA\s+NACIONAL\s+DE\s+HABILITA[CÇ][AÃ]O[^\n]*\n(?:[^\n]*\n){0,3}?\s*([A-ZÁÀÂÃÉÊÍÓÔÕÚÜÇ]{2,}(?:\s+[A-ZÁÀÂÃÉÊÍÓÔÕÚÜÇ]{2,}){2,5})(?:\s+\d{1,2}/\d{1,2}/\d{4})?\s*$",
        r"(?:^|\n)\s*(?:1\s*)?NOME\s*[:\-]?\s*\n?\s*([A-ZÁÀÂÃÉÊÍÓÔÕÚÜÇ]{2,}(?:\s+[A-ZÁÀÂÃÉÊÍÓÔÕÚÜÇ]{2,}){1,5})(?:\n|$)",
    ], t, re.I | re.M)

    # Seleciona a melhor linha em caixa alta, descartando cabeçalhos oficiais.
    if not nome or any(word in nome.upper() for word in ["REPÚBLICA", "MINISTÉRIO", "SECRETARIA", "CARTEIRA", "NACIONAL"]):
        blocked = {"REPÚBLICA", "FEDERATIVA", "BRASIL", "MINISTÉRIO", "TRANSPORTES", "SECRETARIA", "NACIONAL", "TRÂNSITO", "SENATRAN", "CARTEIRA", "HABILITAÇÃO", "DRIVER", "LICENSE", "PERMISO", "CONDUCCIÓN"}
        candidates = []
        for line in t.splitlines():
            clean = _clean(line).upper()
            clean = re.sub(r"\s+\d{1,2}/\d{1,2}/\d{4}.*$", "", clean)
            if not re.fullmatch(r"[A-ZÁÀÂÃÉÊÍÓÔÕÚÜÇ ]{8,60}", clean):
                continue
            words = clean.split()
            if not (2 <= len(words) <= 6):
                continue
            if any(word in blocked for word in words):
                continue
            candidates.append(clean)
        if candidates:
            # Prefere três ou mais palavras; normalmente é o nome completo do condutor.
            candidates.sort(key=lambda value: (len(value.split()) >= 3, len(value)), reverse=True)
            nome = candidates[0]

    # Zona de leitura mecânica como fallback confiável.
    mrz_data = _parse_cnh_mrz(t)
    if not nome and mrz_data["nome"]:
        nome = mrz_data["nome"]
    if not nascimento and mrz_data["data_nascimento"]:
        nascimento = mrz_data["data_nascimento"]
    if not validade and mrz_data["validade_cnh"]:
        validade = mrz_data["validade_cnh"]

    # Datas podem sair sem zero à esquerda; normaliza para DD/MM/AAAA.
    def normalize_date(value):
        if not value:
            return ""
        parts = value.split("/")
        if len(parts) == 3:
            return f"{int(parts[0]):02d}/{int(parts[1]):02d}/{parts[2]}"
        return value

    # Se o candidato de nome parecer ruído e a MRZ tiver nome, prioriza a MRZ.
    if mrz_data["nome"]:
        nome_words = (nome or "").split()
        if not nome or len(nome_words) < 2 or any(len(word) == 1 for word in nome_words):
            nome = mrz_data["nome"]

    validade = normalize_date(validade)
    nascimento = normalize_date(nascimento)

    # Se a validade não veio pela legenda, usa a data futura mais distante.
    dates = re.findall(r"\b\d{1,2}/\d{1,2}/\d{4}\b", t)
    normalized_dates = [normalize_date(value) for value in dates]
    if not validade and normalized_dates:
        try:
            from datetime import datetime
            validade = max(normalized_dates, key=lambda value: datetime.strptime(value, "%d/%m/%Y"))
        except Exception:
            validade = normalized_dates[-1]

    return {
        "nome": nome,
        "cpf": cpf,
        "numero_cnh": registro,
        "categoria": categoria,
        "data_nascimento": nascimento,
        "validade_cnh": validade,
        "texto_extraido": text,
    }

def parse_crlv(text):
    t = _normalize(text)
    upper = t.upper()

    lines = [_clean(line) for line in t.splitlines() if _clean(line)]

    placa = first([
        r"\b([A-Z]{3}[0-9][A-Z0-9][0-9]{2})\b",
    ], upper)

    renavam = first([
        r"(?:C[ÓO]DIGO\s+)?RENAVAM\s*[:\-]?\s*(\d{9,11})",
    ], upper)
    if not renavam:
        candidatos = re.findall(r"(?<!\d)(\d{9,11})(?!\d)", upper)
        for candidato in candidatos:
            renavam = candidato
            break

    chassi = first([
        r"\b([A-HJ-NPR-Z0-9]{17})\b",
    ], upper)

    cpf_cnpj = first([
        r"\b(\d{2}[.]\d{3}[.]\d{3}/\d{4}-\d{2})\b",
        r"\b(\d{3}[.]\d{3}[.]\d{3}-\d{2})\b",
    ], upper)

    ano_fab = ""
    ano_mod = ""
    year_pairs = re.findall(r"\b(19\d{2}|20\d{2})\s+(19\d{2}|20\d{2})\b", upper)
    if year_pairs:
        ano_fab, ano_mod = year_pairs[0]
    else:
        years = re.findall(r"\b(19\d{2}|20\d{2})\b", upper)
        if len(years) >= 2:
            ano_fab, ano_mod = years[0], years[1]

    modelo = ""
    ignore_model = (
        "MARCA / MODELO", "MARCA/MODELO", "PLACA ANTERIOR",
        "CPF / CNPJ", "COMBUSTÍVEL", "SECRETARIA", "REPÚBLICA",
        "CERTIFICADO", "CARTEIRA DIGITAL"
    )
    for line in lines:
        u = line.upper()
        if "/" in u and any(ch.isdigit() for ch in u) and any(ch.isalpha() for ch in u):
            if not any(token in u for token in ignore_model) and not re.search(r"\d{2}[.]\d{3}[.]\d{3}/\d{4}-\d{2}", u):
                modelo = line
                break

    cores = [
        "BRANCO", "BRANCA", "PRETO", "PRETA", "PRATA", "CINZA",
        "VERMELHO", "VERMELHA", "AZUL", "VERDE", "AMARELO",
        "AMARELA", "MARROM", "BEGE", "DOURADO", "DOURADA"
    ]
    cor = ""
    combustivel = ""
    for line in lines:
        u = line.upper()
        for cor_item in cores:
            if u.startswith(cor_item + " "):
                cor = cor_item.title()
                combustivel = line[len(cor_item):].strip(" -/")
                break
        if cor:
            break

    if not modelo:
        modelo = first([
            r"(?:MARCA\s*/\s*MODELO(?:\s*/\s*VERS[AÃ]O)?)\s*[:\-]?\s*([^\n]+)"
        ], t)

    if not cor:
        cor = first([
            r"COR\s+PREDOMINANTE\s*[:\-]?\s*([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ]+)"
        ], upper)

    if not combustivel:
        combustivel = first([
            r"COMBUST[IÍ]VEL\s*[:\-]?\s*([^\n]+)"
        ], t)

    proprietario = ""
    if cpf_cnpj:
        cpf_index = next((i for i, line in enumerate(lines) if cpf_cnpj in line), None)
        if cpf_index is not None:
            for i in range(cpf_index - 1, max(-1, cpf_index - 5), -1):
                candidate = lines[i]
                u = candidate.upper()
                if (
                    len(candidate) >= 5
                    and not re.fullmatch(r"[\d.*\-/ ]+", candidate)
                    and "NÃO APLICÁVEL" not in u
                    and "NAO APLICAVEL" not in u
                    and not re.search(r"\b[A-Z]{3}[0-9][A-Z0-9][0-9]{2}\b", u)
                ):
                    proprietario = candidate
                    break

    return {
        "placa": placa,
        "renavam": renavam,
        "chassi": chassi,
        "marca_modelo": modelo,
        "ano_fabricacao": ano_fab,
        "ano_modelo": ano_mod,
        "cor": cor,
        "combustivel": combustivel,
        "proprietario_legal": proprietario,
        "cpf_cnpj_proprietario": cpf_cnpj,
        "texto_extraido": text,
    }
