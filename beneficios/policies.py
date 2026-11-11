"""Política de sesión con los parámetros vigentes; nunca depende de usuarios o sesiones."""
from functools import lru_cache
from dataclasses import dataclass
from urllib.parse import urlencode, urlsplit
from django.conf import settings
from django.http import QueryDict
from django.urls import reverse
from .forms import MovementFilterForm


@dataclass(frozen=True)
class SessionPolicy:
    idle_seconds: int
    max_seconds: int

    def clock(self, now, created, last):
        return {
            'now': int(now * 1000),
            'idle': int((last + self.idle_seconds) * 1000),
            'absolute': int((created + self.max_seconds) * 1000),
            'warning': min(60_000, self.idle_seconds * 500, self.max_seconds * 500),
        }


@lru_cache(maxsize=4)
def _session_policy(idle_seconds, max_seconds):
    return SessionPolicy(idle_seconds, max_seconds)


def session_policy():
    from .parameters import current
    return _session_policy(current().session_idle_seconds, settings.SESSION_MAX_SECONDS)


def session_return_path(target):
    """Solo se retoman vistas de lectura y filtros de movimientos válidos."""
    if not target or len(target) > 1024 or not target.startswith('/') or target.startswith('//'):
        return ''
    try:
        parsed = urlsplit(target)
    except ValueError:
        return ''
    readable = ('inicio', 'saldo', 'movimientos', 'seguimiento', 'comercios', 'perfil', 'tarjeta', 'ayuda',
                'actividad_cuenta', 'reportar_problema', 'reportes_admin', 'admin_usuarios')
    if parsed.path not in {reverse(name) for name in readable}:
        return ''
    if parsed.path != reverse('movimientos') or not parsed.query:
        return parsed.path
    form = MovementFilterForm(QueryDict(parsed.query))
    if not form.is_valid():
        return parsed.path
    filters = {key: value for key, value in form.cleaned_data.items() if value}
    return f'{parsed.path}?{urlencode(filters)}' if filters else parsed.path
