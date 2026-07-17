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


def _ocr_image(image):
    try:
        import pytesseract
        from PIL import ImageEnhance, ImageFilter, ImageOps

        if shutil.which("tesseract") is None:
            return ""

        image = image.convert("L")
        image = ImageOps.autocontrast(image)
        image = ImageEnhance.Contrast(image).enhance(1.7)
        image = image.filter(ImageFilter.SHARPEN)

        configs = [
            "--oem 3 --psm 6",
            "--oem 3 --psm 11",
        ]
        outputs = []
        for config in configs:
            try:
                outputs.append(pytesseract.image_to_string(image, lang="por", config=config))
            except Exception:
                outputs.append(pytesseract.image_to_string(image, config=config))
        return "\n".join(outputs)
    except Exception:
        return ""


def _ocr_pdf(data):
    try:
        import fitz
        from PIL import Image

        document = fitz.open(stream=data, filetype="pdf")
        outputs = []
        for page_index in range(min(len(document), 2)):
            page = document[page_index]
            pixmap = page.get_pixmap(matrix=fitz.Matrix(3.0, 3.0), alpha=False)
            image = Image.open(io.BytesIO(pixmap.tobytes("png")))

            # OCR da página completa.
            outputs.append(_ocr_image(image))

            # Nas CNHs-e da Senatran, a carteira fica normalmente no lado esquerdo.
            width, height = image.size
            cnh_crop = image.crop((0, 0, int(width * 0.52), int(height * 0.82)))
            outputs.append(_ocr_image(cnh_crop))

            # A faixa inferior contém a zona de leitura mecânica e ajuda a validar o nome.
            mrz_crop = image.crop((0, int(height * 0.68), int(width * 0.55), height))
            outputs.append(_ocr_image(mrz_crop))

        return _normalize("\n".join(part for part in outputs if part))
    except Exception:
        return ""


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
        r"\b\d{9,12}\s+([A-E])\b",
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

    # Zona de leitura mecânica como fallback confiável para o nome.
    mrz = re.search(r"\n([A-Z]{2,}(?:<+[A-Z]{2,}){1,6})<*\n", upper)
    mrz_name = _clean(mrz.group(1).replace("<", " ")) if mrz else ""
    if mrz_name and 2 <= len(mrz_name.split()) <= 6:
        nome = mrz_name

    # Datas podem sair sem zero à esquerda; normaliza para DD/MM/AAAA.
    def normalize_date(value):
        if not value:
            return ""
        parts = value.split("/")
        if len(parts) == 3:
            return f"{int(parts[0]):02d}/{int(parts[1]):02d}/{parts[2]}"
        return value

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
    placa = first([
        r"PLACA\s*[:\-]?\s*([A-Z]{3}[0-9][A-Z0-9][0-9]{2})",
        r"\b([A-Z]{3}[0-9][A-Z][0-9]{2})\b",
    ], t)
    renavam = first([r"(?:C[ÓO]DIGO\s+)?RENAVAM\s*[:\-]?\s*(\d{9,11})"], t)
    chassi = first([r"CHASSI\s*[:\-]?\s*([A-HJ-NPR-Z0-9]{17})"], t)
    modelo = first([r"(?:MARCA\s*/\s*MODELO|MARCA/MODELO)\s*[:\-]?\s*([^\n]+)"], t)
    ano_fab = first([r"ANO\s+FABRICA[CÇ][AÃ]O\s*[:\-]?\s*(\d{4})"], t)
    ano_mod = first([r"ANO\s+MODELO\s*[:\-]?\s*(\d{4})"], t)
    cor = first([r"COR\s*[:\-]?\s*([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ ]{3,})"], t)
    combustivel = first([r"COMBUST[IÍ]VEL\s*[:\-]?\s*([^\n]+)"], t)
    proprietario = first([r"NOME\s*[:\-]?\s*([^\n]+)"], t)
    doc = first([r"CPF\s*/\s*CNPJ\s*[:\-]?\s*([0-9.\-/]{11,18})"], t)
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
        "cpf_cnpj_proprietario": doc,
        "texto_extraido": text,
    }
