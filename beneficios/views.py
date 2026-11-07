from datetime import timedelta
from time import perf_counter
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.core.paginator import Paginator, EmptyPage
from django.db import DatabaseError, transaction
from django.db.models import Case, Count, When
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from .balance_snapshot import last_confirmed_balance, remember_balance, snapshot_key
from .database_access import read_alias
from .events import record
from .forms import LoginForm, MovementFilterForm, ServiceStateForm
from .models import AuditEvent, BenefitAccount, Movement, ServiceInterruption, ServiceState
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


@require_GET
@protected()
def inicio(request):
    return _benefit_page(request, 'dashboard.html', 'inicio')


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
    now = timezone.now().timestamp()
    key = f'pending_retry_{code}'
    last = request.session.get(key, 0)
    if now - last < settings.QUERY_RETRY_SECONDS:
        response = RejectedResponseCreator().create_response(
            request, f'Se debe esperar {settings.QUERY_RETRY_SECONDS} segundos antes de reintentar.',
            http_status=429, **last_confirmed_balance(balance_key))
        response['Retry-After'] = str(settings.QUERY_RETRY_SECONDS)
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
        return PendingResponseCreator().create_response(
            request, audit_recorded=logged, **last_confirmed_balance(balance_key))
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
        try:
            page = paginator.page(form.cleaned_data.get('page') or 1)
        except EmptyPage:
            return {'items': [], 'page': form.cleaned_data.get('page') or 1,
                    'pages': paginator.num_pages, 'total': paginator.count}
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


def _interruption_summary():
    now = timezone.now()
    periods = ServiceInterruption.objects.annotate(
        pending_count=Count('pending_queries'),
    ).order_by(Case(When(restored_at__isnull=True, then=0), default=1), '-started_at', '-pk')[:25]
    for period in periods:
        seconds = max(0, int(((period.restored_at or now) - period.started_at).total_seconds()))
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        period.elapsed = f'{hours:02d}:{minutes:02d}:{seconds:02d}'
    return periods


@require_GET
@protected(administrator=True)
def seguimiento(request):
    audit = AuditEvent.objects.all()
    events = audit.select_related('actor')
    event_type = request.GET.get('event_type', '')
    outcome = request.GET.get('outcome', '')
    if event_type in AuditEvent.Type.values:
        events = events.filter(event_type=event_type)
    if outcome in AuditEvent.Outcome.values:
        events = events.filter(outcome=outcome)
    dates = MovementFilterForm({'desde': request.GET.get('from_date', ''), 'hasta': request.GET.get('to_date', '')})
    if dates.is_valid():
        if dates.cleaned_data.get('desde'):
            events = events.filter(created_at__date__gte=dates.cleaned_data['desde'])
        if dates.cleaned_data.get('hasta'):
            events = events.filter(created_at__date__lte=dates.cleaned_data['hasta'])
    elif request.GET.get('from_date') or request.GET.get('to_date'):
        messages.error(request, 'El rango de fechas no es válido. Se muestran los registros sin ese filtro.')
    day_events = AuditEvent.objects.filter(created_at__gte=timezone.now() - timedelta(hours=24))
    counts = {row['outcome']: row['total'] for row in day_events.values('outcome').annotate(total=Count('id'))}
    stats = {'total': sum(counts.values()), 'success': counts.get('success', 0),
             'interrupted': counts.get('pending', 0), 'denied': counts.get('denied', 0)}
    event_types = set(audit.order_by().values_list('event_type', flat=True).distinct())
    outcomes = set(audit.order_by().values_list('outcome', flat=True).distinct())
    return render(request, 'seguimiento.html', {
        'events': Paginator(events, 25).get_page(request.GET.get('page')),
        'stats': stats, 'services': ServiceState.objects.order_by('code'), 'active_page': 'seguimiento',
        'interruptions': _interruption_summary(),
        'event_type': event_type, 'outcome': outcome,
        'from_date': request.GET.get('from_date', ''), 'to_date': request.GET.get('to_date', ''),
        'filters': {'event_type': event_type, 'outcome': outcome,
                    'from_date': request.GET.get('from_date', ''), 'to_date': request.GET.get('to_date', '')},
        'event_types': [(value, label) for value, label in AuditEvent.Type.choices
                        if value in event_types or value == event_type],
        'outcomes': [(value, label) for value, label in AuditEvent.Outcome.choices
                     if value in outcomes or value == outcome],
    })


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
