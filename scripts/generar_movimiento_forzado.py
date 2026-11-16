"""Genera static/css/movimiento-forzado.css a partir de las animaciones del portal.

Las animaciones están dentro de bloques «@media (prefers-reduced-motion: no-preference)», que el
navegador apaga cuando el sistema operativo pide reducir el movimiento. En equipos compartidos
(por ejemplo, de un instituto) esa opción suele venir activada y no se puede cambiar. Este script
copia esas mismas reglas bajo html[data-motion-force="on"], que se activa solo si el usuario marca
«Mostrar animaciones aunque el sistema pida reducir el movimiento» en Apariencia.

Uso: python scripts/generar_movimiento_forzado.py   (se vuelve a ejecutar si cambian las animaciones)
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS_DIR = ROOT / 'static' / 'css'
OUTPUT = CSS_DIR / 'movimiento-forzado.css'
SKIP = {OUTPUT.name}
ATTRIBUTE = '[data-motion-force="on"]'
MEDIA = re.compile(r'@media\s*\(\s*prefers-reduced-motion\s*:\s*no-preference\s*\)\s*(?:and\s*([^{]*?))?\s*\{')


def _strip_comments(text):
    return re.sub(r'/\*.*?\*/', '', text, flags=re.S)


def _block_end(text, open_index):
    """Índice de la llave que cierra la que está en open_index (ignora llaves dentro de cadenas)."""
    depth, i, quote = 0, open_index, None
    while i < len(text):
        char = text[i]
        if quote:
            if char == '\\':
                i += 2
                continue
            if char == quote:
                quote = None
        elif char in '"\'':
            quote = char
        elif char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError('Llaves sin cerrar en el CSS.')


def _split_selectors(selector):
    """Separa una lista de selectores por las comas de primer nivel (no las de :is() o :not())."""
    parts, depth, current = [], 0, ''
    for char in selector:
        if char in '([':
            depth += 1
        elif char in ')]':
            depth -= 1
        if char == ',' and depth == 0:
            parts.append(current.strip())
            current = ''
        else:
            current += char
    parts.append(current.strip())
    return [part for part in parts if part]


def _scope(selector):
    if selector.startswith('html'):
        return 'html' + ATTRIBUTE + selector[4:]
    if selector.startswith(':root'):
        return ':root' + ATTRIBUTE + selector[5:]
    if selector.startswith('::'):
        return 'html' + ATTRIBUTE + selector
    return f'html{ATTRIBUTE} {selector}'


def _rules(inner):
    """Reescribe las reglas de un bloque: selectores con el atributo; @keyframes y similares sin cambios."""
    out, i = [], 0
    while True:
        open_index = inner.find('{', i)
        if open_index == -1:
            break
        prelude = inner[i:open_index].strip()
        close = _block_end(inner, open_index)
        body = inner[open_index + 1:close]
        if prelude.startswith(('@media', '@supports', '@container')):
            out.append(f'{prelude} {{\n{_rules(body)}}}\n')
        elif prelude.startswith('@'):
            out.append(f'{prelude} {{{body}}}\n')
        else:
            scoped = ',\n'.join(_scope(part) for part in _split_selectors(prelude))
            out.append(f'{scoped} {{{body.strip()}}}\n')
        i = close + 1
    tail = inner[i:].strip()
    if tail:  # Declaraciones sueltas (por ejemplo, @view-transition { navigation: auto; } en una línea).
        out.append(tail + '\n')
    return ''.join(out)


def generate():
    sections = []
    for path in sorted(CSS_DIR.glob('*.css')):
        if path.name in SKIP:
            continue
        text = _strip_comments(path.read_text(encoding='utf-8'))
        blocks = []
        for match in MEDIA.finditer(text):
            open_index = match.end() - 1
            inner = text[open_index + 1:_block_end(text, open_index)]
            rules = _rules(inner)
            extra = (match.group(1) or '').strip()
            blocks.append(f'@media {extra} {{\n{rules}}}\n' if extra else rules)
        if blocks:
            sections.append(f'/* {path.name} */\n' + ''.join(blocks))
    header = ('/* Generado por scripts/generar_movimiento_forzado.py. No editar a mano.\n'
              '   Repite las animaciones del portal bajo html[data-motion-force="on"], para mostrarlas aunque el\n'
              '   sistema pida reducir el movimiento (opción de Apariencia, desactivada por defecto). */\n')
    return header + '\n'.join(sections)


if __name__ == '__main__':
    OUTPUT.write_text(generate(), encoding='utf-8')
    print('Generado', OUTPUT.relative_to(ROOT))
