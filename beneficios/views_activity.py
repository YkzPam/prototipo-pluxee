"""Historial personal de accesos registrados por el prototipo."""
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .models import AuditEvent
from .security import protected
from .views_extra import _beneficiary


ACTIVITY_LABELS = {
    AuditEvent.Type.LOGIN: ('Inicio de sesión', 'Ingreso correcto.'),
    AuditEvent.Type.LOGOUT: ('Cierre de sesión', 'La sesión se cerró voluntariamente.'),
    AuditEvent.Type.EXPIRED: ('Sesión vencida', 'Se registró el vencimiento de la sesión.'),
}

# Estas claves también reconocen los motivos ya guardados en la bitácora.
EXPIRATION_REASONS = {
    'La sesión finalizó por inactividad.': 'La sesión finalizó por inactividad.',
    'La sesión alcanzó su duración máxima y requiere un nuevo ingreso.':
        'La sesión alcanzó su duración máxima.',
}


@require_GET
@protected()
def actividad_cuenta(request):
    _, error = _beneficiary(request)
    if error is not None:
        return error

    events = AuditEvent.objects.filter(actor=request.user).filter(
        Q(event_type__in=(AuditEvent.Type.LOGIN, AuditEvent.Type.LOGOUT), outcome=AuditEvent.Outcome.SUCCESS)
        | Q(event_type=AuditEvent.Type.EXPIRED, outcome=AuditEvent.Outcome.EXPIRED)
    ).values_list('event_type', 'detail', 'created_at')
    page = Paginator(events, 20).get_page(request.GET.get('page'))
    activity = []
    for event_type, detail, created_at in page.object_list:
        title, reason = ACTIVITY_LABELS[event_type]
        if event_type == AuditEvent.Type.EXPIRED:
            reason = EXPIRATION_REASONS.get(detail, reason)
        activity.append({'type': event_type, 'title': title, 'reason': reason, 'created_at': created_at})

    return render(request, 'actividad_cuenta.html', {
        'activity': activity, 'page': page, 'active_page': 'actividad_cuenta',
    })
