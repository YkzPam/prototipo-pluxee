"""Sesiones vigentes y lectura de operaciones administrativas."""
from datetime import datetime, time, timedelta, timezone as dt_timezone
from math import isfinite

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import (
    BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY, get_user_model, logout, update_session_auth_hash,
)
from django.contrib.sessions.models import Session
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.views.decorators.http import require_GET, require_POST

from .events import record
from .models import AuditEvent, Movement, SupportReport
from .policies import session_policy
from .security import protected


def _authenticates(data, user):
    if str(data.get(SESSION_KEY)) != str(user.pk) or data.get(BACKEND_SESSION_KEY) not in settings.AUTHENTICATION_BACKENDS:
        return False
    session_hash = data.get(HASH_SESSION_KEY)
    if not isinstance(session_hash, str) or not session_hash:
        return False
    hashes = (user.get_session_auth_hash(), *user.get_session_auth_fallback_hash())
    return any(constant_time_compare(session_hash, expected) for expected in hashes)


def _session_dates(data, now):
    policy = session_policy()
    dates = {}
    for key, limit in (('auth_started_at', policy.max_seconds), ('last_activity_at', policy.idle_seconds)):
        value = data.get(key)
        if key not in data:
            dates[key] = None
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
            return None
        if value > now or now - value >= limit:
            return None
        try:
            dates[key] = datetime.fromtimestamp(value, tz=dt_timezone.utc)
        except (ValueError, OverflowError, OSError):
            return None
    return dates


def _open_sessions(request):
    now = timezone.now()
    sessions = []
    current_key = request.session.session_key
    for saved in Session.objects.filter(expire_date__gt=now).iterator(chunk_size=200):
        current = saved.session_key == current_key
        data = saved.get_decoded()
        if current:
            saved_start = 'auth_started_at' in data
            data = dict(request.session.items())
            if not saved_start:
                data.pop('auth_started_at', None)
        if not _authenticates(data, request.user):
            continue
        dates = _session_dates(data, now.timestamp())
        if dates is None:
            continue
        sessions.append({
            'current': current, 'started_at': dates['auth_started_at'],
            'last_activity_at': dates['last_activity_at'],
        })
    sessions.sort(key=lambda item: (not item['current'], -(item['last_activity_at'].timestamp() if item['last_activity_at'] else 0)))
    return sessions


@require_GET
@protected()
def sesiones_abiertas(request):
    sessions = _open_sessions(request)
    return render(request, 'sesiones_abiertas.html', {
        'active_page': 'perfil' if not request.user.is_staff else 'seguimiento',
        'sessions': sessions, 'other_sessions': sum(not item['current'] for item in sessions),
    })


class SessionRevocationUnavailable(Exception):
    pass


@require_POST
@protected()
def cerrar_otras_sesiones(request):
    try:
        with transaction.atomic():
            user = get_user_model().objects.select_for_update().get(pk=request.user.pk)
            if not user.is_active or not _authenticates(request.session, user):
                logout(request)
                messages.warning(request, 'El acceso cambió. Ingresa nuevamente para continuar.')
                return redirect('ingresar')
            user.access_revision += 1
            user.save(update_fields=['access_revision'])
            if not record(request, AuditEvent.Type.ACCESS, AuditEvent.Outcome.SUCCESS,
                          'Otras sesiones de la cuenta cerradas.', target_id=user.pk):
                raise SessionRevocationUnavailable
            update_session_auth_hash(request, user)
    except SessionRevocationUnavailable:
        messages.error(request, 'No fue posible cerrar las otras sesiones. Intenta nuevamente.')
    else:
        messages.success(request, 'Se cerraron las otras sesiones. Esta sesión continúa abierta.')
    return redirect('sesiones_abiertas')


def _today_movements():
    today = timezone.localdate()
    start = datetime.combine(today, time.min, tzinfo=timezone.get_current_timezone())
    return today, Movement.objects.filter(occurred_at__gte=start, occurred_at__lt=start + timedelta(days=1))


def operational_summary():
    today, movements = _today_movements()
    report_counts = dict(SupportReport.objects.order_by().values('status').annotate(total=Count('pk')).values_list('status', 'total'))
    received = report_counts.get(SupportReport.Status.RECEIVED, 0)
    review = report_counts.get(SupportReport.Status.REVIEW, 0)
    return {
        'today': today,
        'active_users': get_user_model().objects.filter(is_staff=False, is_superuser=False, is_active=True).count(),
        'today_movements': movements.count(), 'pending_reports': received + review,
        'received_reports': received, 'review_reports': review,
        'active_users_url': reverse('admin_usuarios', query={'estado': 'active'}),
        'movements_url': reverse('movimientos_admin_hoy'),
        'received_url': reverse('reportes_admin', query={'estado': SupportReport.Status.RECEIVED}),
        'review_url': reverse('reportes_admin', query={'estado': SupportReport.Status.REVIEW}),
    }


@require_GET
@protected(administrator=True)
def movimientos_admin_hoy(request):
    today, movements = _today_movements()
    return render(request, 'movimientos_admin_hoy.html', {
        'active_page': 'seguimiento', 'today': today,
        'movements': Paginator(movements.select_related('account__user'), 20).get_page(request.GET.get('page')),
    })
