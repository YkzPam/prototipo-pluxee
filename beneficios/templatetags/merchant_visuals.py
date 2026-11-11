"""Ilustraciones locales por categoría, con rutas fijas."""
import unicodedata

from django import template

register = template.Library()


@register.filter
def merchant_cover(category):
    name = ''.join(char for char in unicodedata.normalize('NFKD', str(category)) if not unicodedata.combining(char)).casefold()
    images = {
        'cafeteria': 'cafe', 'restaurante': 'restaurant', 'supermercado': 'market',
        'almacen': 'grocery', 'panaderia': 'bakery', 'verduleria': 'produce',
    }
    return f'img/merchant-{images.get(name, "grocery")}.svg'
