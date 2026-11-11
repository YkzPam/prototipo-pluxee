"""Ilustraciones locales por categoría, con rutas fijas."""
import unicodedata

from django import template

register = template.Library()


CATEGORY_SLUGS = {
    'cafeteria': 'cafe', 'restaurante': 'restaurant', 'supermercado': 'market',
    'almacen': 'grocery', 'panaderia': 'bakery', 'verduleria': 'produce',
}


def merchant_slug(category):
    """Clave fija de la categoría (sin tildes); las categorías nuevas usan la ilustración de almacén."""
    name = ''.join(char for char in unicodedata.normalize('NFKD', str(category)) if not unicodedata.combining(char)).casefold()
    return CATEGORY_SLUGS.get(name, 'grocery')


@register.filter
def merchant_cover(category):
    return f'img/merchant-{merchant_slug(category)}.svg'
