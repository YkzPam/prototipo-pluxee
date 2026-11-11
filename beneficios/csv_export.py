"""Celdas de texto para archivos que pueden abrirse en una hoja de cálculo."""


def safe_csv_text(value):
    text = str(value)
    # La comilla inicial fuerza texto incluso si la fórmula viene precedida
    # por espacios, saltos de línea o tabulaciones.
    if text.lstrip(' \t\r\n').startswith(('=', '+', '-', '@')) or text.startswith(('\t', '\r', '\n')):
        return "'" + text
    return text
