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


def _ocr_mrz_image(image, timeout=22):
    """OCR especializado para a zona de leitura mecânica da CNH."""
    try:
        import pytesseract
        from PIL import ImageEnhance, ImageFilter, ImageOps

        tesseract_path = shutil.which("tesseract")
        if tesseract_path is None:
            return "[ERRO OCR MRZ: executável tesseract não encontrado]"
        pytesseract.pytesseract.tesseract_cmd = tesseract_path

        image = image.convert("L")
        image = ImageOps.autocontrast(image)
        image = ImageEnhance.Contrast(image).enhance(2.2)
        image = image.resize((image.width * 2, image.height * 2))
        image = image.filter(ImageFilter.SHARPEN)

        config = "--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<"
        try:
            return pytesseract.image_to_string(
                image, lang="eng", config=config, timeout=timeout
            )
        except RuntimeError:
            return f"[ERRO OCR MRZ: tempo máximo de {timeout} segundos excedido]"
        except Exception as exc:
            return f"[ERRO OCR MRZ: {type(exc).__name__}: {exc}]"
    except Exception as exc:
        return f"[ERRO OCR MRZ: {type(exc).__name__}: {exc}]"


def _ocr_cnh_ids_image(image, timeout=18):
    """OCR restrito à linha CPF, número da CNH e categoria."""
    try:
        import pytesseract
        from PIL import ImageEnhance, ImageFilter, ImageOps

        tesseract_path = shutil.which("tesseract")
        if tesseract_path is None:
            return "[ERRO OCR IDS: executável tesseract não encontrado]"
        pytesseract.pytesseract.tesseract_cmd = tesseract_path

        image = image.convert("L")
        image = ImageOps.autocontrast(image)
        image = ImageEnhance.Contrast(image).enhance(2.4)
        image = image.resize((image.width * 3, image.height * 3))
        image = image.filter(ImageFilter.SHARPEN)

        config = (
            "--oem 3 --psm 6 "
            "-c tessedit_char_whitelist=0123456789.-,;:ABCDE "
        )
        try:
            return pytesseract.image_to_string(
                image,
                lang="eng",
                config=config,
                timeout=timeout,
            )
        except RuntimeError:
            return f"[ERRO OCR IDS: tempo máximo de {timeout} segundos excedido]"
        except Exception as exc:
            return f"[ERRO OCR IDS: {type(exc).__name__}: {exc}]"
    except Exception as exc:
        return f"[ERRO OCR IDS: {type(exc).__name__}: {exc}]"


def _ocr_pdf(data):
    """
    OCR leve da CNH-e.

    Lê somente:
      1) faixa CPF + número da CNH + categoria;
      2) zona de leitura mecânica (MRZ).
    """
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

        # Faixa exata onde ficam CPF, registro da CNH e categoria.
        ids_crop = image.crop((
            int(width * 0.225),
            int(height * 0.132),
            int(width * 0.462),
            int(height * 0.164),
        ))

        # MRZ: nome, nascimento e validade.
        mrz_crop = image.crop((
            int(width * 0.065),
            int(height * 0.605),
            int(width * 0.465),
            int(height * 0.700),
        ))

        ids_text = _normalize(_ocr_cnh_ids_image(ids_crop, timeout=18))
        mrz_text = _normalize(_ocr_mrz_image(mrz_crop, timeout=22))

        return _normalize(
            "--- CPF CNH CATEGORIA ---\n" + ids_text +
            "\n\n--- ZONA DE LEITURA MECÂNICA ---\n" + mrz_text
        )
    except Exception as exc:
        return f"[ERRO OCR PDF: {type(exc).__name__}: {exc}]"


def _ocr_crlv_pdf(data):
    """OCR genérico do CRLV somente quando a camada textual estiver ausente."""
    try:
        import fitz
        from PIL import Image

        document = fitz.open(stream=data, filetype="pdf")
        if len(document) == 0:
            return ""

        page = document[0]
        pixmap = page.get_pixmap(matrix=fitz.Matrix(1.8, 1.8), alpha=False)
        image = Image.open(io.BytesIO(pixmap.tobytes("png")))
        return _normalize(_ocr_image(image, psm=6, timeout=35))
    except Exception as exc:
        return f"[ERRO OCR CRLV: {type(exc).__name__}: {exc}]"


def extract_text(file_storage, document_type=None):
    """
    CNH e CRLV possuem fluxos diferentes.

    CNH: camada textual + OCR específico por regiões e MRZ.
    CRLV: prioriza a camada textual digital completa; OCR só como fallback.
    """
    name = (file_storage.filename or "").lower()
    data = file_storage.read()
    file_storage.stream.seek(0)
    digital_text = ""

    if name.endswith(".pdf") or data[:4] == b"%PDF":
        try:
            pdf = PdfReader(io.BytesIO(data), strict=False)
            digital_text = "\n".join((page.extract_text() or "") for page in pdf.pages)
        except Exception as exc:
            digital_text = f"[ERRO TEXTO PDF: {type(exc).__name__}: {exc}]"

        normalized = _normalize(digital_text)
        upper = normalized.upper()

        if document_type == "crlv":
            markers = (
                "CÓDIGO RENAVAM", "CODIGO RENAVAM", "CHASSI",
                "MARCA / MODELO", "CERTIFICADO DE REGISTRO",
            )
            marker_count = sum(marker in upper for marker in markers)
            has_plate = bool(re.search(r"\b[A-Z]{3}[0-9][A-Z0-9][0-9]{2}\b", upper))
            has_chassis = bool(re.search(r"\b[A-HJ-NPR-Z0-9]{17}\b", upper))

            # CRLV-e normalmente já fornece todos os valores na camada textual.
            if marker_count >= 2 or (has_plate and has_chassis) or len(normalized) >= 500:
                return normalized

            return _normalize(
                normalized + "\n\n--- OCR DO CRLV ---\n" + _ocr_crlv_pdf(data)
            )

        if document_type == "cnh":
            return _normalize(
                normalized + "\n\n--- OCR DA IMAGEM ---\n" + _ocr_pdf(data)
            )

        # Detecção automática como segurança.
        if "CÓDIGO RENAVAM" in upper or "CODIGO RENAVAM" in upper or "CHASSI" in upper:
            return normalized
        return _normalize(
            normalized + "\n\n--- OCR DA IMAGEM ---\n" + _ocr_pdf(data)
        )

    try:
        from PIL import Image
        return _normalize(_ocr_image(Image.open(io.BytesIO(data)), psm=6, timeout=35))
    except Exception as exc:
        return f"[ERRO LEITURA: {type(exc).__name__}: {exc}]"


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
    from datetime import date, datetime

    lines = []
    for raw in (text or "").upper().splitlines():
        line = re.sub(r"[^A-Z0-9<]", "", raw)
        if len(line) >= 20 and "<" in line:
            lines.append(line)

    result = {
        "nome": "",
        "data_nascimento": "",
        "validade_cnh": "",
        "linha_documento": "",
    }

    name_lines = [
        line for line in lines
        if "<<" in line
        and not line.startswith("I<BRA")
        and sum(ch.isalpha() for ch in line) >= 8
        and sum(ch.isdigit() for ch in line) <= 2
    ]
    if name_lines:
        line = max(name_lines, key=lambda value: sum(ch.isalpha() for ch in value))
        words = [word for word in re.split(r"<+", line) if len(word) >= 2]
        if 2 <= len(words) <= 8:
            result["nome"] = " ".join(words)

    for line in lines:
        if line.startswith("I<BRA"):
            result["linha_documento"] = line

        match = re.search(r"(\d{6})\d?[MF<](\d{6})\d?", line)
        if not match:
            continue

        def decode(value, expiry=False):
            yy, mm, dd = int(value[:2]), int(value[2:4]), int(value[4:6])
            current_yy = date.today().year % 100
            year = 2000 + yy if expiry or yy <= current_yy else 1900 + yy
            try:
                return datetime(year, mm, dd).strftime("%d/%m/%Y")
            except ValueError:
                return ""

        result["data_nascimento"] = decode(match.group(1), expiry=False)
        result["validade_cnh"] = decode(match.group(2), expiry=True)
        break

    return result


def parse_cnh(text):
    t = _normalize(text)
    upper = t.upper()

    cpf = first([
        r"CPF\s*[:\-]?\s*([0-9.\- ]{11,18})",
        r"\b(\d{3}\.\d{3}\.\d{3}-\d{2})\b",
    ], t)
    cpf_digits = re.sub(r"\D", "", cpf)
    cpf = cpf_digits if len(cpf_digits) == 11 else ""

    registro = first([
        r"(?:N[ºO°]?\s*REGISTRO|REGISTRO)\s*[:\-]?\s*([0-9OIL| ]{9,16})",
        r"(?:N[ºO°]?\s*CNH|CNH)\s*[:\-]?\s*([0-9OIL| ]{9,16})",
        r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\s*[,;:]?\s*([0-9OIL|]{9,12})\b",
        r"\b\d{11}\s*[,;:]?\s*([0-9OIL|]{9,12})\s*[A-E]{1,2}\b",
    ], t)
    if registro:
        registro = registro.upper().translate(str.maketrans({"O": "0", "I": "1", "L": "1", "|": "1"}))
        registro = re.sub(r"\D", "", registro)
        if not (9 <= len(registro) <= 12):
            registro = ""

    validade = first([
        r"VALIDADE\s*[:\-]?\s*(\d{1,2}/\d{1,2}/\d{4})",
        r"DATA\s+VALIDADE\s*[:\-]?\s*(\d{1,2}/\d{1,2}/\d{4})",
    ], t)

    nascimento = first([
        r"(?:DATA\s+E?\s*LOCAL\s+E?UF\s+DE\s+NASCIMENTO|DATA\s+DE\s+NASCIMENTO|NASCIMENTO)\s*[:\-]?\s*\n?\s*(\d{1,2}/\d{1,2}/\d{4})",
        r"\b(\d{1,2}/\d{1,2}/\d{4})\s*,?\s*[A-ZÁÀÂÃÉÊÍÓÔÕÚÜÇ ]{3,},\s*[A-Z]{2}\b",
    ], t)

    categoria = first([
        r"\b\d{3}[.]?\d{3}[.]?\d{3}[-]?\d{2}\s*[,;:]?\s*[|Il ]*\d{9,12}\s+([A-E]{1,2})\b",
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

    # A MRZ identifica o titular; por isso tem prioridade sobre a filiação.
    mrz_data = _parse_cnh_mrz(t)
    if mrz_data["nome"]:
        nome = mrz_data["nome"]
    if mrz_data["data_nascimento"]:
        nascimento = mrz_data["data_nascimento"]
    if mrz_data["validade_cnh"]:
        validade = mrz_data["validade_cnh"]

    # Datas podem sair sem zero à esquerda; normaliza para DD/MM/AAAA.
    def normalize_date(value):
        if not value:
            return ""
        parts = value.split("/")
        if len(parts) == 3:
            return f"{int(parts[0]):02d}/{int(parts[1]):02d}/{parts[2]}"
        return value

    # Corrige truncamentos comuns da MRZ somente quando o OCR superior confirma.
    if nome:
        visible_upper = upper.split("--- ZONA DE LEITURA MECÂNICA ---")[0]
        corrected_words = []
        for word in nome.split():
            candidates = re.findall(rf"\b{re.escape(word)}[A-ZÁÀÂÃÉÊÍÓÔÕÚÜÇ]?\b", visible_upper)
            longer = [candidate for candidate in candidates if len(candidate) == len(word) + 1]
            corrected_words.append(longer[0] if longer else word)
        nome = " ".join(corrected_words)

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

    # Procura o par fabricação/modelo dentro da mesma linha.
    # Isso evita confundir o exercício que aparece junto da placa.
    for line in lines:
        pair = re.fullmatch(r"\s*((?:19|20)\d{2})\s+((?:19|20)\d{2})\s*", line)
        if pair:
            fab, mod = int(pair.group(1)), int(pair.group(2))
            if fab <= mod <= fab + 2:
                ano_fab, ano_mod = str(fab), str(mod)
                break

    if not ano_fab:
        year_pairs = re.findall(r"\b((?:19|20)\d{2})[ \t]+((?:19|20)\d{2})\b", upper)
        for fab_text, mod_text in year_pairs:
            fab, mod = int(fab_text), int(mod_text)
            if fab <= mod <= fab + 2:
                ano_fab, ano_mod = fab_text, mod_text
                break

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
