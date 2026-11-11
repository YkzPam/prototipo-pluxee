from django import template

from beneficios.views_portal import operational_summary

register = template.Library()


@register.inclusion_tag('includes/resumen_operativo.html', takes_context=True)
def resumen_operativo(context):
    request = context.get('request')
    if request is None or not request.user.is_authenticated or not request.user.is_staff:
        return {}
    return {'summary': operational_summary()}
