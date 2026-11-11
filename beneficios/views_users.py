from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from identidad.registration import create_beneficiary

from . import parameters
from .events import log_committed_movement, record
from .forms_extra import ProfileForm
from .forms_users import (AccountCardForm, AccountFilterForm, AccountStateForm, CreditForm, PasswordFields,
                          RegistrationForm)
from .models import AuditEvent, BenefitAccount, DemoCard, Movement
from .security import allow_registration_attempt, protected
from .templatetags.moneda import clp


class AccountActionUnavailable(Exception):
    """El cambio no puede confirmarse y debe revertirse."""


def _audit(request, detail, *, target_id):
    if not record(request, AuditEvent.Type.PROFILE, AuditEvent.Outcome.SUCCESS, detail, target_id=target_id):
        raise AccountActionUnavailable('No fue posible registrar el cambio en la bitácora. Intenta nuevamente.')


def _beneficiaries():
    return get_user_model().objects.filter(is_staff=False, is_superuser=False)


def _registration(request, *, admin):
    initial_credit = parameters.current().registration_initial_credit
    form = RegistrationForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and not admin and not allow_registration_attempt(request):
        form.add_error(None, 'Se alcanzó el límite de intentos de registro. Intenta más tarde.')
        return render(request, 'crear_usuario.html', {
            'form': form, 'initial_credit': initial_credit,
        }, status=429)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                user_id = create_beneficiary(form.cleaned_data)
                _audit(request, 'Cuenta de beneficiario creada.', target_id=user_id)
        except IntegrityError:
            if not get_user_model().objects.filter(username__iexact=form.cleaned_data['username']).exists():
                raise
            form.add_error('username', 'Ese nombre de usuario no está disponible.')
        except AccountActionUnavailable as error:
            form.add_error(None, str(error))
        else:
            if admin:
                messages.success(request, f'Se creó la cuenta con un abono inicial de ${clp(initial_credit)}.')
                return redirect('admin_usuario', user_id=user_id)
            request.session['registration_username'] = form.cleaned_data['username']
            request.session['registration_initial_credit'] = initial_credit
            return redirect('registro_completado')
    return render(request, 'crear_usuario.html', {
        'form': form, 'active_page': 'admin_usuarios', 'initial_credit': initial_credit,
    })


@require_http_methods(['GET', 'POST'])
def crear_usuario(request):
    if request.user.is_authenticated:
        return redirect('admin_crear_usuario' if request.user.is_staff else 'inicio')
    return _registration(request, admin=False)


@require_GET
@never_cache
def registro_completado(request):
    if request.user.is_authenticated:
        return redirect('inicio')
    username = request.session.get('registration_username')
    if not username:
        return redirect('ingresar')
    return render(request, 'registro_completado.html', {
        'username': username, 'initial_credit': request.session.get('registration_initial_credit'),
    })


@require_http_methods(['GET', 'POST'])
@protected(administrator=True)
def admin_crear_usuario(request):
    return _registration(request, admin=True)


USER_ORDERING = {
    'usuario': (F('username').asc(), 'Usuario'),
    'alta': (F('date_joined').desc(), 'Fecha de alta'),
    'ingreso': (F('last_login').desc(nulls_last=True), 'Último ingreso'),
}


def _account_summaries(users):
    """Saldo y estado de tarjeta por usuario. Los montos están cifrados, por eso se suman en Python."""
    accounts = {account.user_id: account for account in
                BenefitAccount.objects.filter(user__in=users).select_related('demo_card')}
    balances = {account.pk: 0 for account in accounts.values()}
    for account_id, kind, amount in Movement.objects.filter(account__in=accounts.values()).order_by().values_list(
            'account_id', 'kind', 'amount').iterator():
        balances[account_id] += amount if kind == Movement.Kind.CREDIT else -amount
    for user in users:
        account = accounts.get(user.pk)
        user.balance = balances.get(account.pk) if account else None
        card = getattr(account, 'demo_card', None) if account else None
        user.card_blocked = card.is_blocked if card else None
    return users


@require_GET
@protected(administrator=True)
def admin_usuarios(request):
    order = request.GET.get('orden') if request.GET.get('orden') in USER_ORDERING else 'usuario'
    users = _beneficiaries().order_by(USER_ORDERING[order][0], 'pk')
    filters = AccountFilterForm(request.GET)
    params = request.GET.copy()
    params.pop('page', None)
    sort_params = params.copy()
    sort_params.pop('orden', None)
    if filters.is_valid():
        query, state = filters.cleaned_data['q'], filters.cleaned_data['estado']
        if query:
            users = users.filter(username__icontains=query)
        if state:
            users = users.filter(is_active=state == 'active')
    page = Paginator(users, 15).get_page(request.GET.get('page'))
    page.object_list = _account_summaries(list(page.object_list))
    return render(request, 'admin_usuarios.html', {
        'active_page': 'admin_usuarios', 'filters': filters, 'users': page, 'filter_query': params.urlencode(),
        'order': order, 'orderings': [(key, label) for key, (_, label) in USER_ORDERING.items()],
        'sort_query': sort_params.urlencode(),
    })


def _credit(request, target, account, values):
    if not target.is_active or account is None:
        raise AccountActionUnavailable('El abono requiere una cuenta de beneficio activa.')
    # Comparte el bloqueo de tarjeta que serializa los cargos de la cuenta.
    if not DemoCard.objects.filter(account=account).update(status=F('status')):
        raise AccountActionUnavailable('La cuenta no tiene una tarjeta de prueba asociada.')
    previous = Movement.objects.filter(credit_reference=values['reference']).first()
    if previous:
        if previous.account_id == account.pk and previous.amount == values['amount']:
            return 'El abono ya estaba registrado.'
        raise AccountActionUnavailable('Esa referencia ya se utilizó. Genera un abono nuevo.')
    movement = Movement.objects.create(
        account=account, kind=Movement.Kind.CREDIT, amount=values['amount'],
        description='Abono administrativo', occurred_at=timezone.now(), credit_reference=values['reference'],
    )
    _audit(request, f'Abono registrado. Movimiento n.º {movement.pk}.', target_id=target.pk)
    log_committed_movement(movement)
    return 'Se registró el abono.'


def _apply_action(request, target, account, action, values):
    if action == 'profile':
        target.first_name = values['first_name']
        target.last_name = values['last_name']
        target.save(update_fields=['first_name', 'last_name'])
        _audit(request, 'Nombre y apellido actualizados.', target_id=target.pk)
        return 'Se guardaron los datos del usuario.'
    if action == 'password':
        target.set_password(values['password1'])
        # La clave asignada por el administrador es temporal: el usuario debe cambiarla al ingresar.
        target.must_change_password = True
        target.access_revision += 1
        target.save(update_fields=['password', 'must_change_password', 'access_revision'])
        _audit(request, 'Contraseña temporal asignada.', target_id=target.pk)
        return ('Se asignó una contraseña temporal y se cerraron las sesiones anteriores. '
                'El usuario deberá cambiarla al ingresar.')
    if action == 'state':
        active = values['state'] == 'active'
        if target.is_active != active:
            if not active and request.POST.get('confirm_deactivation') != '1':
                raise AccountActionUnavailable('Confirma la desactivación para cambiar el acceso.')
            target.is_active = active
            target.access_revision += 1
            target.save(update_fields=['is_active', 'access_revision'])
            _audit(request, 'Acceso activado.' if active else 'Acceso desactivado.', target_id=target.pk)
        return 'Se activó el acceso.' if active else 'Se desactivó el acceso.'
    if action == 'card':
        blocked = values['state'] == 'block'
        updates = {'status': DemoCard.Status.BLOCKED if blocked else DemoCard.Status.ACTIVE, 'changed_at': timezone.now()}
        if blocked:
            updates.update(dynamic_code_digest='', dynamic_expires_at=None)
        if account is None or not DemoCard.objects.filter(account=account).update(**updates):
            raise AccountActionUnavailable('La cuenta no tiene una tarjeta asociada.')
        _audit(request, 'Tarjeta bloqueada por administración.' if blocked else 'Tarjeta activada por administración.',
               target_id=target.pk)
        return 'Se bloqueó la tarjeta.' if blocked else 'Se activó la tarjeta.'
    return _credit(request, target, account, values)


def _user_audit_events(target_id, page_number):
    legacy_details = {
        f'Alta de beneficiario de prueba. Cuenta de usuario #{target_id}.': 'Cuenta creada.',
        f'Datos de prueba editados para el usuario #{target_id}.': 'Nombre y apellido actualizados.',
        f'Contraseña restablecida para el usuario #{target_id}.': 'Contraseña restablecida.',
        f'Acceso activado para el usuario #{target_id}.': 'Acceso activado.',
        f'Acceso desactivado para el usuario #{target_id}.': 'Acceso desactivado.',
    }
    credit_prefix = f'Abono de prueba al usuario #{target_id}. Movimiento #'
    legacy = Q(target__isnull=True, event_type=AuditEvent.Type.PROFILE, outcome=AuditEvent.Outcome.SUCCESS) & (
        Q(detail__in=legacy_details) | Q(detail__startswith=credit_prefix)
    )
    events = AuditEvent.objects.filter(Q(target_id=target_id) | legacy).select_related('actor')
    page = Paginator(events, 15).get_page(page_number)
    for event in page:
        event.operation = event.detail
        if event.target_id is None:
            if event.detail.startswith(credit_prefix):
                event.operation = f'Abono registrado. Movimiento n.º {event.detail.removeprefix(credit_prefix)}'
            else:
                event.operation = legacy_details.get(event.detail, event.detail)
    return page


@require_http_methods(['GET', 'POST'])
@protected(administrator=True)
def admin_usuario(request, user_id):
    target = get_object_or_404(_beneficiaries(), pk=user_id)
    account = getattr(target, 'benefit_account', None)
    action = request.POST.get('action') if request.method == 'POST' else None
    section = request.GET.get('seccion', 'datos')
    if request.method == 'POST':
        section = 'movimientos' if action == 'credit' else 'datos'
    if section not in ('datos', 'movimientos', 'actividad'):
        section = 'datos'
    forms = {
        'profile': ProfileForm(request.POST if action == 'profile' else None, prefix='profile', initial={
            'first_name': target.first_name, 'last_name': target.last_name,
        }),
        'password': PasswordFields(request.POST if action == 'password' else None, prefix='password', user=target),
        'state': AccountStateForm(request.POST if action == 'state' else None, prefix='state', initial={
            'state': 'inactive' if target.is_active else 'active',
        }),
        'credit': CreditForm(request.POST if action == 'credit' else None, prefix='credit'),
        'card': AccountCardForm(request.POST if action == 'card' else None, prefix='card'),
    }
    if request.method == 'POST':
        selected = forms.get(action)
        if selected is None:
            messages.error(request, 'La acción solicitada no está disponible.')
        elif selected.is_valid():
            try:
                with transaction.atomic():
                    locked = get_object_or_404(_beneficiaries().select_for_update(), pk=target.pk)
                    result = _apply_action(request, locked, account, action, selected.cleaned_data)
            except AccountActionUnavailable as error:
                selected.add_error(None, str(error))
            except IntegrityError:
                if action != 'credit' or not Movement.objects.filter(
                    credit_reference=selected.cleaned_data['reference'],
                ).exists():
                    raise
                selected.add_error(None, 'Esa referencia ya se utilizó. Genera un abono nuevo.')
            else:
                messages.success(request, result)
                query = {'seccion': section} if section != 'datos' else None
                return redirect(reverse('admin_usuario', args=[target.pk], query=query))
    movements, activity = None, None
    if section == 'movimientos':
        records = Movement.objects.filter(account=account) if account else Movement.objects.none()
        movements = Paginator(records, 15).get_page(request.GET.get('page'))
    if section == 'actividad':
        activity = _user_audit_events(target.pk, request.GET.get('page'))
    _account_summaries([target])
    return render(request, 'admin_usuario.html', {
        'active_page': 'admin_usuarios', 'target': target, 'account': account,
        'forms': forms, 'section': section, 'movements': movements, 'activity': activity,
    })
