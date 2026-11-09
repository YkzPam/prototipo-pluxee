import csv
from datetime import timedelta
from math import ceil
import re
from time import perf_counter
from urllib.parse import urlencode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.core.paginator import Paginator
from django.db import DatabaseError, transaction
from django.db.models import Case, Count, Q, When
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from .balance_snapshot import last_confirmed_balance, remember_balance, snapshot_key
from .database_access import read_alias
from .events import record
from .forms import LoginForm, MovementFilterForm, ServiceStateForm
from .models import AuditEvent, BenefitAccount, Movement, ServiceInterruption, ServiceState, SERVICE_CODES
from .policies import session_return_path
from .responses import UpdatedResponseCreator, PendingResponseCreator, RejectedResponseCreator
from .security import protected, login_blocked, login_failed, clear_login_failures
from .services import MockDataServiceAdapter, SourceUnavailable


@require_http_methods(['GET', 'POST'])
def ingresar(request):
    next_url = session_return_path(request.POST.get('next', request.GET.get('next', '')))
    if request.user.is_authenticated:
        if request.user.must_change_password:
            return redirect('cambiar_clave')
        return redirect(next_url or 'inicio')
    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        username = form.cleaned_data['username']
        blocked = login_blocked(request, username)
        user = None if blocked else authenticate(request, username=username, password=form.cleaned_data['password'])
        if user is None:
            if not blocked:
                login_failed(request, username)
            record(request, 'login', 'denied', 'Ingreso rechazado por credenciales o límite de intentos.')
            form.add_error(None, 'No fue posible ingresar con esas credenciales. Se deben revisar los datos o intentar más tarde.')
        else:
            login(request, user)
            now = timezone.now()
            request.session['auth_started_at'] = now.timestamp()
            request.session['last_activity_at'] = now.timestamp()
            request.session.set_expiry(now + timedelta(seconds=settings.SESSION_MAX_SECONDS))
            clear_login_failures(request, username)
            record(request, 'login', 'success', 'Ingreso correcto mediante cuenta de prueba.')
            if user.must_change_password:
                return redirect('cambiar_clave')
            return redirect(next_url or 'inicio')
    return render(request, 'login.html', {'form': form, 'next': next_url, 'active_page': 'ingresar'})


@require_POST
@protected()
def salir(request):
    record(request, 'logout', 'success', 'Sesión finalizada voluntariamente.')
    logout(request)
    messages.success(request, 'La sesión se cerró correctamente.')
    return redirect('ingresar')


def _account(request):
    return BenefitAccount.objects.filter(user=request.user).first()


def _benefit_page(request, template, active_page, *, account_context=None):
    if request.user.is_staff:
        return redirect('seguimiento')
    account = _account(request)
    if account is None:
        return render(request, 'error.html', {'title': 'Cuenta no disponible', 'status': 404,
            'message': 'El usuario de prueba no tiene una cuenta de beneficios asociada.'}, status=404)
    context = {'account': account, 'active_page': active_page}
    if account_context:
        context.update(account_context(account))
    return render(request, template, context)


def _interrupted_queries():
    try:
        return list(ServiceState.objects.using(read_alias()).filter(
            available=False, code__in=[code for code, _ in SERVICE_CODES],
        ).order_by('code').values_list('code', flat=True))
    except DatabaseError:
        return None


@require_GET
@protected()
def inicio(request):
    return _benefit_page(request, 'dashboard.html', 'inicio', account_context=lambda _: {
        'interrupted_queries': _interrupted_queries() or [],
    })


@require_GET
@protected(api=True)
def estado_consultas(request):
    interrupted = _interrupted_queries()
    if interrupted is None:
        return PendingResponseCreator().create_response(request, 'No se pudo comprobar el estado de las consultas.')
    return UpdatedResponseCreator().create_response(request, data={'interrupted': interrupted})


@require_GET
@protected()
def saldo(request):
    return _benefit_page(request, 'balance.html', 'saldo')


@require_GET
@protected()
def movimientos(request):
    def account_context(account):
        filters = MovementFilterForm(request.GET)
        current = filters.cleaned_data.get('tipo') if filters.is_valid() else None
        try:
            kinds = set(Movement.objects.using(read_alias()).filter(account_id=account.pk)
                        .order_by().values_list('kind', flat=True).distinct())
        except DatabaseError:
            # La pantalla permanece disponible si la consulta de movimientos no responde.
            kinds = set()
        return {'movement_kinds': [(value, label) for value, label in Movement.Kind.choices
                                   if value in kinds or value == current]}

    return _benefit_page(request, 'movements.html', 'movimientos', account_context=account_context)


def _authorized_account(request, account_id):
    account = BenefitAccount.objects.filter(pk=account_id, user=request.user).first()
    if account is None:
        record(request, 'access', 'denied', 'Consulta de una cuenta ajena o no disponible rechazada.')
    return account


def _retry_limit(request, code, balance_key=None):
    last = request.session.get(f'pending_retry_{code}', 0)
    remaining = ceil(settings.QUERY_RETRY_SECONDS - (timezone.now().timestamp() - last))
    if remaining > 0:
        response = RejectedResponseCreator().create_response(
            request, 'La consulta sigue pendiente y aún no se ha actualizado.',
            http_status=429, **last_confirmed_balance(balance_key))
        response['Retry-After'] = str(remaining)
        return response
    return None


def _query(request, account_id, code, operation):
    start = perf_counter()
    account = _authorized_account(request, account_id)
    if account is None:
        return RejectedResponseCreator().create_response(request)
    balance_key = snapshot_key(request, account) if code == 'balance' else None
    limited = _retry_limit(request, code, balance_key)
    if limited:
        return limited
    try:
        data = operation(account)
    except SourceUnavailable as error:
        request.session[f'pending_retry_{code}'] = timezone.now().timestamp()
        logged = record(request, code, 'pending', 'Fuente académica interrumpida; consulta pendiente sin modificar registros.',
                        int((perf_counter() - start) * 1000), interruption_id=error.interruption_id)
        # Django no guarda automáticamente sesiones en respuestas 5xx. En esta
        # interrupción controlada se conservan la actividad y el límite de reintento.
        request.session.save()
        response = PendingResponseCreator().create_response(
            request, audit_recorded=logged, **last_confirmed_balance(balance_key))
        response['Retry-After'] = str(settings.QUERY_RETRY_SECONDS)
        return response
    request.session.pop(f'pending_retry_{code}', None)
    logged = record(request, code, 'success', 'Consulta autorizada de datos ficticios completada.',
                    int((perf_counter() - start) * 1000))
    updated_at = timezone.now().isoformat()
    if balance_key:
        remember_balance(balance_key, balance=data['balance'], updated_at=updated_at,
                         timeout=request.session.get_expiry_age())
    return UpdatedResponseCreator().create_response(request, data=data, updated_at=updated_at, audit_recorded=logged)


@require_GET
@protected(api=True)
def api_saldo(request, account_id):
    return _query(request, account_id, 'balance', MockDataServiceAdapter().balance)


@require_GET
@protected(api=True)
def api_movimientos(request, account_id):
    form = MovementFilterForm(request.GET)
    if not form.is_valid():
        return RejectedResponseCreator().create_response(
            request, 'Los filtros no son válidos. Se deben revisar las fechas, el tipo y la página.', http_status=400)

    def operation(account):
        query = MockDataServiceAdapter().movements(account, form.cleaned_data)
        paginator = Paginator(query, 20)
        page = paginator.get_page(form.cleaned_data.get('page') or 1)
        return {'items': [{'id': item.pk, 'date': timezone.localtime(item.occurred_at).isoformat(),
                           'description': item.description, 'kind': item.kind, 'amount': item.amount}
                          for item in page], 'page': page.number, 'pages': paginator.num_pages, 'total': paginator.count}

    return _query(request, account_id, 'movements', operation)


@require_http_methods(['GET', 'POST'])
@protected(api=True)
def actividad(request):
    return UpdatedResponseCreator().create_response(request, 'La sesión permanece vigente.',
        expires_at=request.session.get_expiry_date().isoformat(), idle_seconds=settings.SESSION_IDLE_SECONDS)


@require_http_methods(['GET', 'POST'])
@protected()
def cambiar_clave(request):
    if request.method == 'POST':
        with transaction.atomic():
            user = get_user_model().objects.select_for_update().get(pk=request.user.pk)
            form = PasswordChangeForm(user, request.POST)
            if form.is_valid() and form.cleaned_data['old_password'] == form.cleaned_data['new_password1']:
                form.add_error('new_password2', 'La nueva contraseña debe ser distinta de la contraseña actual.')
            if not form.errors:
                form.save(commit=False)
                user.must_change_password = False
                user.save(update_fields=['password', 'must_change_password'])
                record(request, 'password', 'success', 'Contraseña actualizada con la política de validación.')
        if not form.errors:
            update_session_auth_hash(request, user)
            messages.success(request, 'La contraseña se actualizó correctamente.')
            return redirect('inicio')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'change_password.html', {'form': form, 'active_page': 'clave'})


QUERY_EVENT_TYPES = (AuditEvent.Type.BALANCE, AuditEvent.Type.MOVEMENTS)
SUMMARY_FILTERS = {
    'interrupted': {'event_type': 'queries', 'outcome': AuditEvent.Outcome.PENDING},
    'login_denied': {'event_type': AuditEvent.Type.LOGIN, 'outcome': AuditEvent.Outcome.DENIED},
    'access_denied': {'event_type': AuditEvent.Type.ACCESS, 'outcome': AuditEvent.Outcome.DENIED},
    'expired': {'event_type': AuditEvent.Type.EXPIRED, 'outcome': AuditEvent.Outcome.EXPIRED},
}


def _interruption_elapsed(period, now):
    seconds = max(0, int(((period.restored_at or now) - period.started_at).total_seconds()))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f'{hours:02d}:{minutes:02d}:{seconds:02d}'


def _event_type_condition(event_type):
    if event_type == 'queries':
        return Q(event_type__in=QUERY_EVENT_TYPES)
    return Q(event_type=event_type)


def _followup_events(params, now):
    events = AuditEvent.objects.all()
    filters = {name: params.get(name, '') for name in
               ('event_type', 'outcome', 'from_date', 'to_date', 'period', 'interruption')}
    event_type, outcome = filters['event_type'], filters['outcome']
    if event_type in AuditEvent.Type.values or event_type == 'queries':
        events = events.filter(_event_type_condition(event_type))
    else:
        filters['event_type'] = ''
    if outcome in AuditEvent.Outcome.values:
        events = events.filter(outcome=outcome)
    else:
        filters['outcome'] = ''
    if filters['period'] == '24h':
        events = events.filter(created_at__gte=now - timedelta(hours=24))
    else:
        filters['period'] = ''

    dates = MovementFilterForm({'desde': filters['from_date'], 'hasta': filters['to_date']})
    dates_valid = dates.is_valid()
    if dates_valid:
        if dates.cleaned_data.get('desde'):
            events = events.filter(created_at__date__gte=dates.cleaned_data['desde'])
        if dates.cleaned_data.get('hasta'):
            events = events.filter(created_at__date__lte=dates.cleaned_data['hasta'])

    selected_interruption = None
    if filters['interruption']:
        if not re.fullmatch(r'[1-9][0-9]{0,18}', filters['interruption']):
            raise Http404
        selected_interruption = get_object_or_404(
            ServiceInterruption.objects.annotate(pending_count=Count('pending_queries')),
            pk=int(filters['interruption']),
        )
        events = events.filter(interruption=selected_interruption)
    return events, filters, dates_valid, selected_interruption


@require_GET
@protected(administrator=True)
def seguimiento(request):
    now = timezone.now()
    events, filters, dates_valid, selected_interruption = _followup_events(request.GET, now)
    if not dates_valid:
        messages.error(request, 'El rango de fechas no es válido. Se muestran los registros sin ese filtro.')

    day_events = AuditEvent.objects.filter(created_at__gte=now - timedelta(hours=24))
    stats = day_events.aggregate(
        total=Count('id'),
        success=Count('id', filter=Q(outcome=AuditEvent.Outcome.SUCCESS)),
        **{key: Count('id', filter=_event_type_condition(value['event_type']) & Q(outcome=value['outcome']))
           for key, value in SUMMARY_FILTERS.items()},
    )
    interruptions = ServiceInterruption.objects.annotate(pending_count=Count('pending_queries')).order_by(
        Case(When(restored_at__isnull=True, then=0), default=1), '-started_at', '-pk',
    )[:25]
    for period in interruptions:
        period.elapsed = _interruption_elapsed(period, now)
    if selected_interruption:
        selected_interruption.elapsed = _interruption_elapsed(selected_interruption, now)

    audit = AuditEvent.objects.order_by()
    observed_types = set(audit.values_list('event_type', flat=True).distinct())
    if observed_types.intersection(QUERY_EVENT_TYPES):
        observed_types.add('queries')
    observed_types.add(filters['event_type'])
    observed_outcomes = set(audit.values_list('outcome', flat=True).distinct()) | {filters['outcome']}
    event_choices = [('queries', 'Consultas de saldo y movimientos'), *AuditEvent.Type.choices]
    return render(request, 'seguimiento.html', {
        'events': Paginator(events.select_related('actor'), 25).get_page(request.GET.get('page')),
        'stats': stats, 'services': ServiceState.objects.order_by('code'), 'active_page': 'seguimiento',
        'interruptions': interruptions, 'selected_interruption': selected_interruption,
        'filters': filters, 'event_query': urlencode({key: value for key, value in filters.items() if value}),
        'summary_filters': {key: urlencode({'period': '24h', **value}) for key, value in SUMMARY_FILTERS.items()},
        'event_types': [(value, label) for value, label in event_choices if value in observed_types],
        'outcomes': [(value, label) for value, label in AuditEvent.Outcome.choices if value in observed_outcomes],
        'export_available': dates_valid,
    })


@require_GET
@protected(administrator=True)
@never_cache
def seguimiento_exportar(request):
    events, _, dates_valid, _ = _followup_events(request.GET, timezone.now())
    if not dates_valid:
        return HttpResponseBadRequest('El rango de fechas de la exportación no es válido.', content_type='text/plain')

    response = HttpResponse(content_type='text/csv; charset=utf-8',
                            headers={'Content-Disposition': 'attachment; filename="bitacora_pluxee.csv"'})
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow(('Fecha y hora', 'Evento', 'Resultado', 'Duración (ms)'))
    event_labels, outcome_labels = dict(AuditEvent.Type.choices), dict(AuditEvent.Outcome.choices)
    rows = events.values_list('created_at', 'event_type', 'outcome', 'duration_ms').iterator()
    for created_at, event_type, outcome, duration_ms in rows:
        writer.writerow((timezone.localtime(created_at).isoformat(timespec='seconds'),
                         event_labels.get(event_type, 'Otro evento'), outcome_labels.get(outcome, 'Otro resultado'),
                         duration_ms))
    return response


@require_POST
@protected(administrator=True)
@transaction.atomic
def servicios(request):
    form = ServiceStateForm(request.POST)
    if form.is_valid():
        service = ServiceState.objects.select_for_update().filter(code=form.cleaned_data['service']).first()
        if service:
            available = form.cleaned_data['state'] == 'available'
            if available == service.available:
                messages.info(request, 'El servicio de prueba ya está en ese estado.')
                return redirect('seguimiento')
            now = timezone.now()
            if available:
                if service.active_interruption_id:
                    ServiceInterruption.objects.filter(
                        pk=service.active_interruption_id, restored_at__isnull=True,
                    ).update(restored_at=now)
                service.active_interruption_id = None
            else:
                service.active_interruption = ServiceInterruption.objects.create(
                    service_code=service.code, started_at=now,
                )
            service.available = available
            service.save(update_fields=['available', 'changed_at', 'active_interruption'])
            detail = 'restablecido' if available else 'interrumpido'
            record(request, 'service', 'success', f'Servicio de prueba {service.label} {detail} desde administración.')
            messages.success(request, 'El estado del servicio de prueba se actualizó.')
        else:
            messages.error(request, 'El servicio de prueba no existe.')
    else:
        messages.error(request, 'La configuración enviada no es válida.')
    return redirect('seguimiento')


def csrf_failure(request, reason=''):
    return render(request, 'error.html', {'title': 'La solicitud necesita actualizarse', 'status': 403,
        'message': 'La protección del formulario rechazó la solicitud. Se debe recargar la página e intentar nuevamente.'}, status=403)


def permission_error(request, exception=None):
    return render(request, 'error.html', {'title': 'Acceso restringido', 'status': 403,
        'message': 'La cuenta no tiene permiso para realizar esta acción.'}, status=403)


def not_found(request, exception=None):
    return render(request, 'error.html', {'title': 'Página no encontrada', 'status': 404,
        'message': 'La dirección solicitada no está disponible.'}, status=404)


def server_error(request):
    return render(request, 'error.html', {'title': 'No fue posible completar la solicitud', 'status': 500,
        'message': 'Se produjo una dificultad en el prototipo. Se puede volver al inicio e intentar nuevamente.'}, status=500)
