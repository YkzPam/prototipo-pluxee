from django import template

register = template.Library()


@register.filter
def clp(value):
    """Enteros CLP con el mismo separador de miles que Intl es-CL."""
    if value is None:
        return '—'
    try:
        return f'{int(value):,}'.replace(',', '.')
    except (TypeError, ValueError):
        return '—'
