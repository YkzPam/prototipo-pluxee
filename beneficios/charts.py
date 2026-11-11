"""Gráficos de barras como SVG generado en el servidor; la política CSP no admite estilos ni scripts en línea."""
from math import ceil, log10

from .templatetags.moneda import clp

WIDTH, HEIGHT = 720, 220
LEFT, RIGHT, TOP, BOTTOM = 56, 8, 10, 26


def _nice_max(value):
    if value <= 0:
        return 1
    magnitude = 10 ** int(log10(value))
    for step in (1, 2, 2.5, 5, 10):
        if value <= step * magnitude:
            return int(step * magnitude) if step * magnitude >= 1 else 1
    return int(10 * magnitude)


def _n(value):
    # Texto con punto decimal: la plantilla localizaría un float con coma y SVG no lo admite.
    return f'{value:.1f}'


def _label(value, money):
    return f'${clp(value)}' if money else clp(value)


def bar_chart(labels, series, *, stacked=False, money=False, max_labels=12):
    """series: lista de (nombre, clase CSS, valores) con un valor por etiqueta."""
    count = len(labels)
    totals = [sum(values[index] for _, _, values in series) for index in range(count)] if stacked else \
        [max((values[index] for _, _, values in series), default=0) for index in range(count)]
    top = _nice_max(max(totals, default=0))
    plot_w, plot_h = WIDTH - LEFT - RIGHT, HEIGHT - TOP - BOTTOM
    slot = plot_w / max(count, 1)
    group_w = slot * .72
    bars = []
    for index, label in enumerate(labels):
        x0 = LEFT + index * slot + (slot - group_w) / 2
        base = 0
        for position, (name, css, values) in enumerate(series):
            value = values[index]
            height = plot_h * value / top
            if stacked:
                x, width, y = x0, group_w, TOP + plot_h - (base + height)
                base += height
            else:
                width = group_w / len(series)
                x, y = x0 + position * width, TOP + plot_h - height
            if value:
                bars.append({'x': _n(x), 'y': _n(y), 'w': _n(max(width - 1, 1)), 'h': _n(max(height, 1)), 'css': css,
                             'title': f'{label} · {name}: {_label(value, money)}'})
    every = max(1, ceil(count / max_labels))
    x_labels = [{'x': _n(LEFT + index * slot + slot / 2), 'text': label}
                for index, label in enumerate(labels) if index % every == 0]
    y_ticks = [{'y': _n(TOP + plot_h - plot_h * fraction), 'text': _label(int(top * fraction), money)}
               for fraction in (0, .5, 1)]
    return {
        'width': WIDTH, 'height': HEIGHT, 'left': LEFT, 'axis_x': LEFT - 6, 'right': WIDTH - RIGHT,
        'label_y': HEIGHT - 6, 'bars': bars, 'x_labels': x_labels, 'y_ticks': y_ticks,
        'legend': [(name, css, sum(values)) for name, css, values in series], 'money': money,
        'empty': not any(totals),
    }
