from django.conf import settings
from django.db import DatabaseError
from django.utils import timezone
from .models import Notification
from .policies import session_policy


def project_context(request):
    return {'environment_label': settings.ENVIRONMENT_LABEL,
            'session_idle_minutes': session_policy().idle_seconds // 60,
            'session_max_hours': settings.SESSION_MAX_SECONDS // 3600}


def notification_context(request):
    if not request.user.is_authenticated:
        return {}
    try:
        count = Notification.objects.filter(user=request.user, read_at__isnull=True).count()
    except DatabaseError:
        count = None
    return {'notification_unread_count': count}


# Cada página pertenece a un área con color e ilustración propios (ver static/css/identidad.css).
PORTAL_SECTIONS = {
    'beneficio': ('inicio', 'saldo', 'movimientos', 'detalle_movimiento'),
    'pagos': ('pagar', 'comprobante', 'generar_clave_dinamica'),
    'comercios': ('comercios', 'admin_comercios', 'admin_comercio_crear', 'admin_comercio'),
    'cuenta': ('perfil', 'tarjeta', 'apariencia', 'cambiar_clave', 'sesiones_abiertas', 'actividad_cuenta'),
    'ayuda': ('ayuda', 'reportar_problema', 'notificaciones', 'reportes_admin', 'incidencia_admin'),
    'monitoreo': ('seguimiento', 'bitacora', 'movimientos_admin_hoy'),
    'usuarios': ('admin_usuarios', 'admin_crear_usuario', 'admin_usuario'),
    'informes': ('admin_informes',),
    'ajustes': ('admin_parametros',),
}
SECTION_BY_VIEW = {view: section for section, views in PORTAL_SECTIONS.items() for view in views}


def greeting(hour):
    if 5 <= hour < 12:
        return 'Buenos días'
    if 12 <= hour < 20:
        return 'Buenas tardes'
    return 'Buenas noches'


def portal_context(request):
    match = getattr(request, 'resolver_match', None)
    return {'portal_section': SECTION_BY_VIEW.get(getattr(match, 'url_name', None), 'general'),
            'portal_greeting': greeting(timezone.localtime().hour)}
