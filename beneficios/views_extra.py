"""Servicios académicos adicionales, sin conexión con la red real de Pluxee."""
import secrets
import uuid
from datetime import datetime, timedelta
from django.contrib import messages
from django.db import OperationalError, transaction
from django.db.models import F, Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from .events import log_committed_movement, record
from .forms_extra import CardActionForm, DynamicCodeForm, MerchantSearchForm, PaymentForm, ProfileForm
from .models import (BenefitAccount, DemoCard, HelpTopic, Merchant, MerchantFavorite, Movement, Payment,
                     PaymentThrottle)
from .receipt_pdf import receipt_pdf
from .security import protected
from .services import MockDataServiceAdapter, SourceUnavailable


class AuditUnavailable(Exception):
    """Un cargo no se confirma sin su registro de auditoría."""


DYNAMIC_CODE_VALIDITY = timedelta(minutes=90)
PAYMENT_LOCKOUT = timedelta(minutes=15)
PAYMENT_REVIEW_VALIDITY = timedelta(minutes=5)
LEGACY_MERCHANT_DESCRIPTIONS = {
    'Cafetería ficticia para realizar pagos de demostración.': 'Cafetería habilitada para pagos de demostración.',
    'Panadería ficticia para las funciones del prototipo.': 'Panadería del catálogo de demostración.',
}


def _beneficiary(request):
    if request.user.is_staff:
        return None, redirect('seguimiento')
    account = BenefitAccount.objects.filter(user=request.user).first()
    if account is None:
        return None, render(request, 'error.html', {
            'title': 'Cuenta no disponible', 'status': 404,
            'message': 'El usuario de prueba no tiene una cuenta de beneficios asociada.'}, status=404)
    return account, None


@require_GET
@protected()
def comercios(request):
    account, error = _beneficiary(request)
    if error is not None:
        return error
    form = MerchantSearchForm(request.GET)
    merchants = Merchant.objects.filter(active=True)
    if form.is_valid():
        values = form.cleaned_data
        if values.get('q'):
            merchants = merchants.filter(Q(name__icontains=values['q']) | Q(code__icontains=values['q']))
        if values.get('categoria'):
            merchants = merchants.filter(category=values['categoria'])
        if values.get('comuna'):
            merchants = merchants.filter(commune=values['comuna'])
    else:
        merchants = merchants.none()
    favorite_ids = list(MerchantFavorite.objects.filter(user=request.user).values_list('merchant_id', flat=True))
    if request.GET.get('favoritos') == '1':
        merchants = merchants.filter(pk__in=favorite_ids)
    items = list(merchants)
    for item in items:
        item.is_favorite = item.pk in favorite_ids
        if item.address.startswith('Dirección ficticia ') and item.address.endswith(', sin ubicación real'):
            item.address = 'Ubicación de referencia para la demostración'
        item.description = LEGACY_MERCHANT_DESCRIPTIONS.get(item.description, item.description)
    return render(request, 'comercios.html', {
        'form': form, 'merchants': items, 'favorite_ids': favorite_ids, 'account': account,
        'q': request.GET.get('q', ''), 'categoria': request.GET.get('categoria', ''),
        'comuna': request.GET.get('comuna', ''), 'favorites_only': request.GET.get('favoritos') == '1',
        'categories': form.fields['categoria'].choices, 'communes': form.fields['comuna'].choices,
        'active_page': 'comercios',
    }, status=200 if form.is_valid() else 400)


@require_POST
@protected()
@transaction.atomic
def favorito(request, merchant_id):
    _, error = _beneficiary(request)
    if error is not None:
        return error
    merchant = get_object_or_404(Merchant, pk=merchant_id, active=True)
    existing = MerchantFavorite.objects.filter(user=request.user, merchant=merchant)
    if existing.exists():
        existing.delete()
        messages.success(request, 'El comercio se quitó de favoritos.')
    else:
        MerchantFavorite.objects.get_or_create(user=request.user, merchant=merchant)
        messages.success(request, 'El comercio se agregó a favoritos.')
    form = MerchantSearchForm(request.GET)
    query = {name: value for name, value in form.cleaned_data.items() if value} if form.is_valid() else {}
    if request.GET.get('favoritos') == '1':
        query['favoritos'] = '1'
    return redirect(reverse('comercios', query=query))


def _lock_payment_card(card):
    # En SQLite la escritura adquiere el bloqueo antes de leer el saldo o la
    # clave. En MySQL bloquea la misma fila que usa el cambio de estado.
    DemoCard.objects.filter(pk=card.pk).update(status=F('status'))
    card.refresh_from_db()


def _payment_credential(request, now, matches, failure):
    throttle, _ = PaymentThrottle.objects.get_or_create(user=request.user, defaults={'window_started': now})
    if throttle.blocked_until and throttle.blocked_until > now:
        record(request, 'payment', 'denied', 'Validación académica rechazada por límite temporal de intentos.')
        return throttle, 'La validación está bloqueada temporalmente. Se debe esperar quince minutos desde el bloqueo.', 429
    if throttle.blocked_until or now - throttle.window_started >= PAYMENT_LOCKOUT:
        throttle.failures = 0
        throttle.window_started = now
        throttle.blocked_until = None
    if not matches():
        throttle.failures += 1
        if throttle.failures >= 5:
            throttle.blocked_until = now + PAYMENT_LOCKOUT
        throttle.save()
        record(request, 'payment', 'denied', 'La credencial de demostración no se pudo validar.')
        return throttle, failure, 400
    return throttle, None, 200


def _reset_payment_attempts(throttle, now):
    throttle.failures = 0
    throttle.blocked_until = None
    throttle.window_started = now
    throttle.save()


def _dynamic_digest(request, card, code):
    value = f'{card.account_id}:{request.session.session_key}:{code}'
    return salted_hmac('pluxee.demo.dynamic-payment', value, algorithm='sha256').hexdigest()


def _payment_authorization(request, values, card):
    credential = card.dynamic_code_digest if values['method'] == Payment.Method.DYNAMIC else card.pin_hash
    fields = (request.user.pk, request.session.session_key, card.pk, card.changed_at.isoformat(),
              values['merchant'].pk, values['amount'], values['method'], values['idempotency_key'], credential)
    return salted_hmac('pluxee.payment-review', ':'.join(map(str, fields)), algorithm='sha256').hexdigest()


def _payment_result(request, values, account, card, *, review_only=False, authorization=None,
                    expected_balance=None):
    """Serializa cargos de una cuenta y confirma libro y comprobante juntos."""
    with transaction.atomic():
        _lock_payment_card(card)
        method = values['method']
        previous = Payment.objects.filter(user=request.user, idempotency_key=values['idempotency_key']).first()
        if previous:
            if (previous.amount == values['amount'] and previous.merchant_id == values['merchant'].pk
                    and previous.method == method):
                return previous, None, 200
            record(request, 'payment', 'denied', 'Referencia de pago ya utilizada con datos distintos.')
            return None, 'La referencia ya se utilizó para otra compra. Se debe iniciar un nuevo pago.', 409
        if not Merchant.objects.filter(pk=values['merchant'].pk, active=True).exists():
            return None, 'El comercio ya no está disponible.', 400
        try:
            MockDataServiceAdapter.check_service('movements', database='default')
            balance = MockDataServiceAdapter(use_primary=True).balance(account)['balance']
        except SourceUnavailable:
            record(request, 'payment', 'pending', 'Pago académico sin procesar por interrupción de la fuente de datos.')
            return None, 'El servicio de consulta está interrumpido. No se realizó ningún cargo. Se puede reintentar cuando vuelva a estar disponible.', 503
        if card.is_blocked:
            record(request, 'payment', 'denied', 'Pago rechazado por tarjeta bloqueada.')
            return None, 'La tarjeta está bloqueada. Se debe activar antes de pagar.', 409
        now = timezone.now()
        if authorization is not None:
            def matches():
                dynamic_valid = method != Payment.Method.DYNAMIC or (
                    card.dynamic_expires_at and now < card.dynamic_expires_at and card.dynamic_code_digest
                )
                return bool(dynamic_valid) and constant_time_compare(
                    authorization, _payment_authorization(request, values, card),
                )

            invalid = 'La autorización cambió o venció. Revisa el pago nuevamente.'
        elif method == Payment.Method.DYNAMIC:
            def matches():
                return (request.session.session_key and card.dynamic_expires_at and now < card.dynamic_expires_at
                        and constant_time_compare(card.dynamic_code_digest, _dynamic_digest(request, card, values['dynamic_code'])))

            invalid = 'La clave dinámica no coincide, venció o ya se utilizó. Puedes generar otra.'
        else:
            def matches():
                return card.check_pin(values['pin'])

            invalid = 'El PIN de demostración no es válido. No se realizó ningún cargo.'
        throttle, failure, status = _payment_credential(request, now, matches, invalid)
        if failure:
            return None, failure, status
        if values['amount'] > balance:
            record(request, 'payment', 'denied', 'Pago rechazado por saldo insuficiente.')
            return None, 'El monto supera el saldo disponible. No se realizó ningún cargo.', 400
        if expected_balance is not None and balance != expected_balance:
            return None, 'El saldo cambió desde la revisión. Revisa los datos del pago nuevamente.', 409
        _reset_payment_attempts(throttle, now)
        if review_only:
            return {'balance': balance, 'authorization': _payment_authorization(request, values, card)}, None, 200
        movement = Movement.objects.create(
            account=account, kind=Movement.Kind.DEBIT, amount=values['amount'],
            description=f'Compra en {values["merchant"].name}'[:120], occurred_at=now)
        payment = Payment.objects.create(
            user=request.user, account=account, merchant=values['merchant'], movement=movement,
            amount=values['amount'], balance_after=balance - values['amount'],
            idempotency_key=values['idempotency_key'], method=method)
        if method == Payment.Method.DYNAMIC:
            card.dynamic_code_digest = ''
            card.dynamic_expires_at = None
            card.save(update_fields=['dynamic_code_digest', 'dynamic_expires_at'])
        if not record(request, 'payment', 'success', 'Pago académico confirmado con un único cargo y comprobante.'):
            # La excepción sale de atomic: nunca conservar solo una parte de
            # cargo, comprobante y registro obligatorio del pago.
            raise AuditUnavailable
        log_committed_movement(movement)
        return payment, None, 200


def _payment_page(request, form, account, card, method, *, status=200, dynamic_form=None,
                  issued_code=None, issued_expires_at=None, review=None, payment_error=None):
    if review is not None:
        balance = review['balance']
    else:
        try:
            balance = MockDataServiceAdapter().balance(account)['balance']
        except SourceUnavailable:
            balance = None
    selected_merchant = getattr(form, 'cleaned_data', {}).get('merchant') or form['merchant'].value()
    selected_merchant_id = getattr(selected_merchant, 'pk', selected_merchant)
    return render(request, 'pagar.html', {
        'form': form, 'account': account, 'card': card, 'method': method,
        'balance': balance, 'merchants': Merchant.objects.filter(active=True),
        'selected_merchant_id': selected_merchant_id, 'active_page': 'pagar',
        'dynamic_form': dynamic_form if dynamic_form is not None else DynamicCodeForm(prefix='clave'),
        'issued_code': issued_code, 'issued_expires_at': issued_expires_at,
        'review': review,
        'payment_error': payment_error,
    }, status=status)


def _payment_initial(method, merchant_id):
    initial = {'idempotency_key': uuid.uuid4(), 'method': method}
    if merchant_id.isascii() and merchant_id.isdecimal() and len(merchant_id) <= 12:
        initial['merchant'] = merchant_id
        if method == Payment.Method.QR:
            initial['qr_code'] = Merchant.objects.filter(pk=merchant_id, active=True).values_list('code', flat=True).first()
    return initial


def _store_payment_review(request, values, checked, account):
    now = timezone.now()
    reviews = {key: value for key, value in request.session.get('payment_reviews', {}).items()
               if value['expires_at'] > now.timestamp()}
    # Acotar el estado de las pestañas abiertas sin conservar credenciales.
    reviews = dict(list(reviews.items())[-4:])
    token = secrets.token_urlsafe(32)
    reviews[token] = {
        'user_id': request.user.pk, 'account_id': account.pk,
        'merchant_id': values['merchant'].pk, 'amount': values['amount'], 'method': values['method'],
        'idempotency_key': str(values['idempotency_key']), 'balance': checked['balance'],
        'authorization': checked['authorization'], 'expires_at': (now + PAYMENT_REVIEW_VALIDITY).timestamp(),
    }
    request.session['payment_reviews'] = reviews
    return token


def _payment_review_details(token, stored, values):
    return {
        'token': token, 'merchant': values['merchant'], 'amount': stored['amount'],
        'balance': stored['balance'], 'balance_after': stored['balance'] - stored['amount'],
        'method_label': dict(Payment.Method.choices)[stored['method']],
        'expires_at': datetime.fromtimestamp(stored['expires_at'], tz=timezone.get_current_timezone()),
    }


def _review_payment_action(request, account, card):
    token = request.POST.get('review_token', '') if request.method == 'POST' else request.GET.get('revision', '')
    stored = request.session.get('payment_reviews', {}).get(token)
    form = PaymentForm(initial=_payment_initial(Payment.Method.ONLINE, ''))
    if (not stored or stored['user_id'] != request.user.pk or stored['account_id'] != account.pk
            or stored['expires_at'] <= timezone.now().timestamp()):
        return _payment_page(request, form, account, card, Payment.Method.ONLINE, status=409,
                             payment_error='La revisión venció o ya no está disponible. Ingresa los datos del pago nuevamente.')
    merchant = Merchant.objects.filter(pk=stored['merchant_id'], active=True).first()
    values = {'merchant': merchant, 'amount': stored['amount'], 'method': stored['method'],
              'idempotency_key': uuid.UUID(stored['idempotency_key'])}
    initial = {**values, 'merchant': stored['merchant_id']}
    if stored['method'] == Payment.Method.QR and merchant:
        initial['qr_code'] = merchant.code
    form = PaymentForm(initial=initial)
    if request.method == 'GET' and merchant is not None:
        return _payment_page(request, form, account, card, stored['method'],
                             review=_payment_review_details(token, stored, values))
    if request.POST.get('payment_step') == 'edit':
        reviews = request.session['payment_reviews']
        reviews.pop(token)
        request.session['payment_reviews'] = reviews
        return _payment_page(request, form, account, card, stored['method'])
    if merchant is None:
        return _payment_page(request, form, account, card, stored['method'], status=409,
                             payment_error='El comercio ya no está disponible. Elige otro comercio.')
    try:
        payment, failure, status = _payment_result(
            request, values, account, card, authorization=stored['authorization'], expected_balance=stored['balance'],
        )
    except (AuditUnavailable, OperationalError):
        payment, failure, status = None, 'No fue posible confirmar el pago. Puedes volver a intentar esta misma confirmación.', 503
    if payment:
        return redirect('comprobante', payment_id=payment.pk)
    if status >= 500:
        request.session.save()
        return _payment_page(request, form, account, card, stored['method'], status=status,
                             review=_payment_review_details(token, stored, values), payment_error=failure)
    return _payment_page(request, form, account, card, stored['method'], status=status, payment_error=failure)


@require_http_methods(['GET', 'POST'])
@protected()
@never_cache
def pagar(request):
    account, error = _beneficiary(request)
    if error is not None:
        return error
    card = DemoCard.objects.filter(account=account).first()
    if card is None:
        return render(request, 'error.html', {'title': 'Tarjeta no disponible', 'status': 404,
            'message': 'La cuenta no tiene una tarjeta de demostración disponible.'}, status=404)
    if request.method == 'POST' and request.POST.get('payment_step') in ('confirm', 'edit'):
        return _review_payment_action(request, account, card)
    if request.method == 'GET' and request.GET.get('revision'):
        return _review_payment_action(request, account, card)
    method = (request.POST.get('method') if request.method == 'POST' else request.GET.get('metodo'))
    if method not in Payment.Method.values:
        method = Payment.Method.ONLINE
    initial = _payment_initial(method, request.GET.get('comercio', ''))
    form = PaymentForm(request.POST if request.method == 'POST' else None, initial=initial)
    http_status = 200
    if request.method == 'POST':
        if form.is_valid():
            review_only = request.POST.get('payment_step') == 'review'
            try:
                payment, failure, http_status = _payment_result(
                    request, form.cleaned_data, account, card, review_only=review_only,
                )
            except AuditUnavailable:
                payment, failure, http_status = None, 'No fue posible completar el registro del pago. No se realizó ningún cargo. Se puede reintentar la misma solicitud.', 503
            except OperationalError:
                payment, failure, http_status = None, 'La operación está ocupada. Se puede reintentar la misma solicitud sin generar un cargo duplicado.', 503
            if payment:
                if review_only and isinstance(payment, dict):
                    token = _store_payment_review(request, form.cleaned_data, payment, account)
                    return redirect(reverse('pagar', query={'revision': token}))
                return redirect('comprobante', payment_id=payment.pk)
            form.add_error(None, failure)
            if http_status >= 500:
                # Conservar la actividad de una interrupción controlada: Django
                # no guarda automáticamente la sesión de respuestas 5xx.
                request.session.save()
        else:
            http_status = 400
    return _payment_page(request, form, account, card, method, status=http_status)


def _issue_dynamic_code(request, card, pin):
    with transaction.atomic():
        _lock_payment_card(card)
        if card.is_blocked:
            return None, None, 'La tarjeta está bloqueada. Se debe activar para generar una clave.', 409
        if not request.session.session_key:
            return None, None, 'Ingresa nuevamente para generar una clave.', 403
        now = timezone.now()
        throttle, failure, status = _payment_credential(
            request, now, lambda: card.check_pin(pin), 'El PIN de demostración no es válido.',
        )
        if failure:
            return None, None, failure, status
        code = f'{secrets.randbelow(10000):04d}'
        expires_at = now + DYNAMIC_CODE_VALIDITY
        card.dynamic_code_digest = _dynamic_digest(request, card, code)
        card.dynamic_expires_at = expires_at
        card.save(update_fields=['dynamic_code_digest', 'dynamic_expires_at'])
        _reset_payment_attempts(throttle, now)
        if not record(request, 'card', 'success', 'Clave dinámica académica generada.'):
            raise AuditUnavailable
        return code, expires_at, None, 200


@require_POST
@protected()
def generar_clave_dinamica(request):
    account, error = _beneficiary(request)
    if error is not None:
        return error
    card = get_object_or_404(DemoCard, account=account)
    dynamic_form = DynamicCodeForm(request.POST, prefix='clave')
    code, expires_at, status = None, None, 400
    if dynamic_form.is_valid():
        try:
            code, expires_at, failure, status = _issue_dynamic_code(request, card, dynamic_form.cleaned_data['pin'])
        except (AuditUnavailable, OperationalError):
            failure, status = 'La clave no se pudo generar. Puedes volver a intentarlo.', 503
            request.session.save()
        if failure:
            dynamic_form.add_error(None, failure)
    method = Payment.Method.DYNAMIC
    form = PaymentForm(initial=_payment_initial(method, request.POST.get('comercio', '')))
    return _payment_page(request, form, account, card, method, status=status, dynamic_form=dynamic_form,
                         issued_code=code, issued_expires_at=expires_at)


@require_GET
@protected()
def comprobante(request, payment_id, *, download=False):
    account, error = _beneficiary(request)
    if error is not None:
        return error
    payment = Payment.objects.select_related('merchant', 'movement').filter(pk=payment_id, user=request.user, account=account).first()
    if payment is None:
        record(request, 'access', 'denied', 'Comprobante de pago ajeno o inexistente rechazado.')
        return render(request, 'error.html', {'title': 'Comprobante no disponible', 'status': 404,
            'message': 'No se encontró un comprobante disponible para esta cuenta.'}, status=404)
    if download:
        return FileResponse(receipt_pdf(payment, account), as_attachment=True,
                            filename=f'comprobante-{payment.pk}.pdf', content_type='application/pdf')
    return render(request, 'comprobante.html', {'payment': payment, 'account': account, 'active_page': 'pagar'})


@require_http_methods(['GET', 'POST'])
@protected()
def perfil(request):
    account, error = _beneficiary(request)
    if error is not None:
        return error
    form = ProfileForm(request.POST if request.method == 'POST' else None, initial={
        'first_name': request.user.first_name, 'last_name': request.user.last_name})
    if request.method == 'POST' and form.is_valid():
        request.user.first_name = form.cleaned_data['first_name']
        request.user.last_name = form.cleaned_data['last_name']
        with transaction.atomic():
            request.user.save(update_fields=['first_name', 'last_name'])
            record(request, 'profile', 'success', 'Nombre y apellido del perfil actualizados.')
        messages.success(request, 'El perfil de demostración se actualizó correctamente.')
        return redirect('perfil')
    return render(request, 'perfil.html', {'form': form, 'account': account,
                  'card': DemoCard.objects.filter(account=account).first(), 'active_page': 'perfil'},
                  status=400 if request.method == 'POST' and not form.is_valid() else 200)


@require_http_methods(['GET', 'POST'])
@protected()
def tarjeta(request):
    account, error = _beneficiary(request)
    if error is not None:
        return error
    card = get_object_or_404(DemoCard, account=account)
    if request.method == 'POST':
        form = CardActionForm(request.POST)
        if form.is_valid():
            new_status = DemoCard.Status.BLOCKED if form.cleaned_data['action'] == 'block' else DemoCard.Status.ACTIVE
            with transaction.atomic():
                updates = {'status': new_status, 'changed_at': timezone.now()}
                if new_status == DemoCard.Status.BLOCKED:
                    updates.update(dynamic_code_digest='', dynamic_expires_at=None)
                DemoCard.objects.filter(pk=card.pk).update(**updates)
                record(request, 'card', 'success', 'Tarjeta ' + ('bloqueada.' if new_status == DemoCard.Status.BLOCKED else 'activada.'))
            messages.success(request, 'El estado de la tarjeta se actualizó.')
            return redirect('tarjeta')
        messages.error(request, 'La acción enviada no es válida.')
        return render(request, 'tarjeta.html', {'card': card, 'account': account, 'active_page': 'tarjeta'}, status=400)
    return render(request, 'tarjeta.html', {'card': card, 'account': account, 'active_page': 'tarjeta'})


@require_GET
@protected()
def ayuda(request):
    account, error = _beneficiary(request)
    if error is not None:
        return error
    faqs = HelpTopic.objects.filter(active=True).values('question', 'answer')
    return render(request, 'ayuda.html', {'faqs': faqs, 'account': account, 'active_page': 'ayuda'})
