from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, KeepTogether
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.colors import black, HexColor
from reportlab.platypus import Image
import qrcode


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont('Helvetica', 8)
    canvas.drawCentredString(A4[0]/2, 10*mm, f'Página {doc.page}')
    canvas.restoreState()


def gerar_pdf_contrato(numero_contrato: str, texto: str, codigo_publico: str | None=None, url_validacao: str | None=None) -> bytes:
    buffer=BytesIO()
    doc=SimpleDocTemplate(buffer,pagesize=A4,rightMargin=22*mm,leftMargin=22*mm,topMargin=20*mm,bottomMargin=18*mm,title=numero_contrato,author='Frota Fácil')
    styles=getSampleStyleSheet()
    normal=ParagraphStyle('Contrato',parent=styles['BodyText'],fontName='Helvetica',fontSize=10.2,leading=15,alignment=TA_JUSTIFY,spaceAfter=5,textColor=black)
    titulo=ParagraphStyle('Titulo',parent=styles['Heading1'],fontName='Helvetica-Bold',fontSize=13,leading=17,alignment=TA_CENTER,spaceAfter=12)
    heading=ParagraphStyle('Clausula',parent=styles['Heading2'],fontName='Helvetica-Bold',fontSize=10.5,leading=14,spaceBefore=8,spaceAfter=5)
    story=[]
    if url_validacao:
        qr_buffer=BytesIO()
        qrcode.make(url_validacao).save(qr_buffer,format='PNG')
        qr_buffer.seek(0)
        story.append(Image(qr_buffer,width=24*mm,height=24*mm,hAlign='RIGHT'))
        if codigo_publico:
            story.append(Paragraph(f'<b>Validação:</b> {codigo_publico}',ParagraphStyle('Codigo',parent=normal,alignment=TA_CENTER,spaceAfter=6,textColor=HexColor('#334155'))))
    linhas=[x.rstrip() for x in (texto or '').splitlines()]
    assinatura=[]
    em_assinaturas=False
    for linha in linhas:
        s=linha.strip()
        if not s:
            if em_assinaturas: assinatura.append(Spacer(1,4*mm))
            else: story.append(Spacer(1,2.5*mm))
            continue
        if s.startswith('________________________________'):
            em_assinaturas=True
        target=assinatura if em_assinaturas else story
        safe=s.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
        if s.startswith('CONTRATO PARTICULAR'):
            target.append(Paragraph(safe,titulo))
            target.append(Paragraph(f'<b>{numero_contrato}</b>',ParagraphStyle('Numero',parent=normal,alignment=TA_CENTER,spaceAfter=8)))
        elif s.startswith('CLÁUSULA ') or s=='IDENTIFICAÇÃO DAS PARTES':
            target.append(Paragraph(safe,heading))
        else:
            target.append(Paragraph(safe,normal))
    if assinatura:
        story.append(PageBreak())
        story.append(KeepTogether(assinatura))
    doc.build(story,onFirstPage=_footer,onLaterPages=_footer)
    return buffer.getvalue()
