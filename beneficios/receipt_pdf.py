"""Comprobante descargable de una operación simulada del portal."""
from io import BytesIO
from xml.sax.saxutils import escape

from django.utils import timezone
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph

from .templatetags.moneda import clp


def receipt_pdf(payment, account):
    output = BytesIO()
    pdf = Canvas(output, pagesize=letter)
    pdf.setTitle('Comprobante de pago simulado')
    pdf.setAuthor('Portal de beneficios')
    width, height = letter
    left, right = 52, width - 52
    content_width = right - left
    ink = HexColor('#27173A')
    purple = HexColor('#3B195F')
    muted = HexColor('#61556E')

    pdf.setFillColor(purple)
    pdf.roundRect(left, height - 166, content_width, 114, 17, fill=1, stroke=0)
    pdf.setFillColor(HexColor('#D4ED75'))
    pdf.setFont('Helvetica-Bold', 10)
    pdf.drawString(left + 24, height - 85, 'PORTAL DE BENEFICIOS')
    pdf.setFillColor(HexColor('#FFFFFF'))
    pdf.setFont('Helvetica-Bold', 25)
    pdf.drawString(left + 24, height - 119, 'Comprobante de pago')
    pdf.setFont('Helvetica', 12)
    pdf.drawString(left + 24, height - 143, 'Operación simulada registrada')

    pdf.setFillColor(HexColor('#F0E9F8'))
    pdf.roundRect(left, height - 253, content_width, 66, 13, fill=1, stroke=0)
    pdf.setFillColor(muted)
    pdf.setFont('Helvetica-Bold', 10)
    pdf.drawString(left + 22, height - 212, 'MONTO EN PESOS CHILENOS')
    pdf.setFillColor(ink)
    pdf.setFont('Helvetica-Bold', 24)
    pdf.drawString(left + 22, height - 239, f'${clp(payment.amount)}')

    rows = (
        ('Comercio', payment.merchant.name),
        ('Código de comercio', payment.merchant.code),
        ('Medio de pago', payment.get_method_display()),
        ('Fecha y hora', timezone.localtime(payment.created_at).strftime('%d/%m/%Y a las %H:%M:%S')),
        ('Cuenta', f'Terminada en {account.number_suffix}'),
        ('Saldo después del pago', f'${clp(payment.balance_after)}'),
        ('Número de operación', str(payment.pk)),
    )
    y = height - 278
    style = ParagraphStyle('ReceiptValue', fontName='Helvetica', fontSize=11, leading=15, textColor=ink)
    for label, value in rows:
        pdf.setFillColor(muted)
        pdf.setFont('Helvetica-Bold', 10)
        pdf.drawString(left + 4, y - 11, label)
        paragraph = Paragraph(escape(str(value)), style)
        _, block_height = paragraph.wrap(content_width - 180, 75)
        paragraph.drawOn(pdf, left + 172, y - block_height)
        y -= max(block_height, 15) + 18
        pdf.setStrokeColor(HexColor('#E4DCEB'))
        pdf.line(left, y + 8, right, y + 8)

    pdf.setFillColor(purple)
    pdf.setFont('Helvetica-Bold', 10)
    pdf.drawString(left, y - 25, 'PAGO SIMULADO · SIN VALOR COMERCIAL')
    pdf.setFillColor(muted)
    pdf.setFont('Helvetica', 10)
    pdf.drawString(left, y - 43, 'Conserva el número de operación para identificar este movimiento.')
    pdf.showPage()
    pdf.save()
    output.seek(0)
    return output
