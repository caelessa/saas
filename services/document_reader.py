import io, re
from pathlib import Path
from pypdf import PdfReader

def _clean(v): return re.sub(r'\s+', ' ', v or '').strip()
def _digits(v): return re.sub(r'\D', '', v or '')

def extract_text(file_storage):
    name=(file_storage.filename or '').lower(); data=file_storage.read(); file_storage.stream.seek(0)
    text=''
    if name.endswith('.pdf'):
        try:
            reader=PdfReader(io.BytesIO(data)); text='\n'.join((p.extract_text() or '') for p in reader.pages)
        except Exception: pass
        if len(text.strip()) < 80:
            try:
                import fitz, pytesseract
                from PIL import Image
                doc=fitz.open(stream=data, filetype='pdf')
                pages=[]
                for i in range(min(len(doc),2)):
                    pix=doc[i].get_pixmap(matrix=fitz.Matrix(1.4,1.4), alpha=False)
                    img=Image.open(io.BytesIO(pix.tobytes('png')))
                    pages.append(pytesseract.image_to_string(img, lang='por'))
                text='\n'.join(pages)
            except Exception: pass
    else:
        try:
            import pytesseract
            from PIL import Image
            text=pytesseract.image_to_string(Image.open(io.BytesIO(data)), lang='por')
        except Exception: pass
    return text

def first(patterns,text,flags=re.I):
    for p in patterns:
        m=re.search(p,text,flags)
        if m: return _clean(m.group(1))
    return ''

def parse_cnh(text):
    t=text.replace('\r','\n')
    cpf=first([r'CPF\s*[:\-]?\s*([0-9.\-]{11,14})',r'\b(\d{3}\.\d{3}\.\d{3}-\d{2})\b'],t)
    registro=first([r'(?:N[ºO°]?\s*REGISTRO|REGISTRO)\s*[:\-]?\s*(\d{9,12})',r'\b(\d{11})\b'],t)
    validade=first([r'VALIDADE\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})'],t)
    nascimento=first([r'(?:DATA DE NASCIMENTO|NASCIMENTO)\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})'],t)
    categoria=first([r'CATEGORIA\s*[:\-]?\s*([A-E]{1,2})\b',r'CAT\.?(?:EGORIA)?\s*[:\-]?\s*([A-E]{1,2})\b'],t)
    nome=first([r'NOME\s*[:\-]?\s*([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ ]{5,})\n',r'1\s*NOME\s*\n([^\n]{5,})'],t)
    return {'nome':nome,'cpf':cpf,'numero_cnh':registro,'categoria':categoria,'data_nascimento':nascimento,'validade_cnh':validade,'texto_extraido':text}

def parse_crlv(text):
    t=text.replace('\r','\n')
    placa=first([r'PLACA\s*[:\-]?\s*([A-Z]{3}[0-9][A-Z0-9][0-9]{2})',r'\b([A-Z]{3}[0-9][A-Z][0-9]{2})\b'],t)
    renavam=first([r'(?:C[ÓO]DIGO\s+)?RENAVAM\s*[:\-]?\s*(\d{9,11})'],t)
    chassi=first([r'CHASSI\s*[:\-]?\s*([A-HJ-NPR-Z0-9]{17})'],t)
    modelo=first([r'(?:MARCA\s*/\s*MODELO|MARCA/MODELO)\s*[:\-]?\s*([^\n]+)'],t)
    anos=first([r'ANO\s+FABRICA[CÇ][AÃ]O\s*[:\-]?\s*(\d{4}).{0,30}ANO\s+MODELO\s*[:\-]?\s*(\d{4})'],t,re.I|re.S)
    ano_fab=first([r'ANO\s+FABRICA[CÇ][AÃ]O\s*[:\-]?\s*(\d{4})'],t)
    ano_mod=first([r'ANO\s+MODELO\s*[:\-]?\s*(\d{4})'],t)
    cor=first([r'COR\s*[:\-]?\s*([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ ]{3,})'],t)
    combustivel=first([r'COMBUST[IÍ]VEL\s*[:\-]?\s*([^\n]+)'],t)
    proprietario=first([r'NOME\s*[:\-]?\s*([^\n]+)'],t)
    doc=first([r'CPF\s*/\s*CNPJ\s*[:\-]?\s*([0-9.\-/]{11,18})'],t)
    return {'placa':placa,'renavam':renavam,'chassi':chassi,'marca_modelo':modelo,'ano_fabricacao':ano_fab,'ano_modelo':ano_mod,'cor':cor,'combustivel':combustivel,'proprietario_legal':proprietario,'cpf_cnpj_proprietario':doc,'texto_extraido':text}
