"""Servicios académicos adicionales, sin conexión con la red real de Pluxee."""
import uuid
from datetime import timedelta
from django.contrib import messages
from django.db import OperationalError, transaction
from django.db.models import F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from .events import record
from .forms_extra import CardActionForm, MerchantSearchForm, PaymentForm, ProfileForm
from .models import BenefitAccount, DemoCard, Merchant, MerchantFavorite, Movement, Payment, PaymentThrottle
from .security import protected
from .services import MockDataServiceAdapter, SourceUnavailable


class AuditUnavailable(Exception):
    """Un cargo no se confirma sin su registro de auditoría."""


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
        messages.success(request, 'El comercio de prueba se quitó de favoritos.')
    else:
        MerchantFavorite.objects.get_or_create(user=request.user, merchant=merchant)
        messages.success(request, 'El comercio de prueba se agregó a favoritos.')
    return redirect('comercios')


def _payment_result(request, values, account, card):
    """Serializa cargos de una cuenta y confirma libro y comprobante juntos."""
    with transaction.atomic():
        # La primera operación dentro de la transacción es una escritura. En
        # SQLite esto adquiere el bloqueo antes de leer el saldo; select_for_update
        # por sí solo no bloquea filas en ese motor. En otros motores bloquea la
        # fila de la tarjeta. Bloqueo/activación emplea la misma fila.
        DemoCard.objects.filter(pk=card.pk).update(status=F('status'))
        card.refresh_from_db()
        previous = Payment.objects.filter(user=request.user, idempotency_key=values['idempotency_key']).first()
        if previous:
            if previous.amount == values['amount'] and previous.merchant_id == values['merchant'].pk:
                return previous, None, 200
            record(request, 'payment', 'denied', 'Referencia de pago ya utilizada con datos distintos.')
            return None, 'La referencia ya se utilizó para otro monto o comercio. Se debe iniciar un nuevo pago.', 409
        if not Merchant.objects.filter(pk=values['merchant'].pk, active=True).exists():
            return None, 'El comercio de prueba ya no está disponible.', 400
        try:
            MockDataServiceAdapter.check_service('movements', database='default')
            balance = MockDataServiceAdapter(use_primary=True).balance(account)['balance']
        except SourceUnavailable:
            record(request, 'payment', 'pending', 'Pago académico sin procesar por interrupción de la fuente de datos.')
            return None, 'El servicio de consulta está interrumpido. No se realizó ningún cargo. Se puede reintentar cuando vuelva a estar disponible.', 503
        if card.is_blocked:
            record(request, 'payment', 'denied', 'Pago académico rechazado por tarjeta de prueba bloqueada.')
            return None, 'La tarjeta de prueba está bloqueada. Se debe activar antes de pagar.', 409
        now = timezone.now()
        throttle, _ = PaymentThrottle.objects.get_or_create(user=request.user, defaults={'window_started': now})
        if throttle.blocked_until and throttle.blocked_until > now:
            record(request, 'payment', 'denied', 'Pago académico rechazado por límite temporal de intentos.')
            return None, 'El ingreso del PIN está bloqueado temporalmente. Se debe esperar quince minutos desde el bloqueo.', 429
        if (throttle.blocked_until and throttle.blocked_until <= now) or now - throttle.window_started >= timedelta(minutes=15):
            throttle.failures = 0
            throttle.window_started = now
            throttle.blocked_until = None
        if not card.check_pin(values['pin']):
            throttle.failures += 1
            if throttle.failures >= 5:
                throttle.blocked_until = now + timedelta(minutes=15)
            throttle.save()
            record(request, 'payment', 'denied', 'Pago académico rechazado por validación del PIN de prueba.')
            return None, 'El PIN de demostración no es válido. No se realizó ningún cargo.', 400
        if values['amount'] > balance:
            record(request, 'payment', 'denied', 'Pago académico rechazado por saldo de prueba insuficiente.')
            return None, 'El monto supera el saldo disponible. No se realizó ningún cargo.', 400
        throttle.failures = 0
        throttle.blocked_until = None
        throttle.window_started = now
        throttle.save()
        movement = Movement.objects.create(
            account=account, kind=Movement.Kind.DEBIT, amount=values['amount'],
            description=f'Pago de prueba: {values["merchant"].name}'[:120], occurred_at=now)
        payment = Payment.objects.create(
            user=request.user, account=account, merchant=values['merchant'], movement=movement,
            amount=values['amount'], balance_after=balance - values['amount'],
            idempotency_key=values['idempotency_key'])
        if not record(request, 'payment', 'success', 'Pago académico confirmado con un único cargo y comprobante.'):
            # La excepción sale de atomic: nunca conservar solo una parte de
            # cargo, comprobante y registro obligatorio del pago.
            raise AuditUnavailable
        return payment, None, 200


@require_http_methods(['GET', 'POST'])
@protected()
def pagar(request):
    account, error = _beneficiary(request)
    if error is not None:
        return error
    card = DemoCard.objects.filter(account=account).first()
    if card is None:
        return render(request, 'error.html', {'title': 'Tarjeta no disponible', 'status': 404,
            'message': 'La cuenta no tiene una tarjeta de demostración disponible.'}, status=404)
    initial = {'idempotency_key': uuid.uuid4()}
    merchant_id = request.GET.get('comercio', '')
    if merchant_id.isdigit() and len(merchant_id) <= 12:
        initial['merchant'] = merchant_id
    form = PaymentForm(request.POST if request.method == 'POST' else None, initial=initial)
    http_status = 200
    if request.method == 'POST':
        if form.is_valid():
            try:
                payment, failure, http_status = _payment_result(request, form.cleaned_data, account, card)
            except AuditUnavailable:
                payment, failure, http_status = None, 'No fue posible completar el registro del pago. No se realizó ningún cargo. Se puede reintentar la misma solicitud.', 503
            except OperationalError:
                payment, failure, http_status = None, 'La operación está ocupada. Se puede reintentar la misma solicitud sin generar un cargo duplicado.', 503
            if payment:
                return redirect('comprobante', payment_id=payment.pk)
            form.add_error(None, failure)
            if http_status >= 500:
                # Conservar la actividad de una interrupción controlada: Django
                # no guarda automáticamente la sesión de respuestas 5xx.
                request.session.save()
        else:
            http_status = 400
    try:
        balance = MockDataServiceAdapter().balance(account)['balance']
    except SourceUnavailable:
        balance = None
    return render(request, 'pagar.html', {'form': form, 'account': account, 'card': card,
        'balance': balance, 'merchants': Merchant.objects.filter(active=True), 'active_page': 'pagar'}, status=http_status)


@require_GET
@protected()
def comprobante(request, payment_id):
    account, error = _beneficiary(request)
    if error is not None:
        return error
    payment = Payment.objects.select_related('merchant', 'movement').filter(pk=payment_id, user=request.user, account=account).first()
    if payment is None:
        record(request, 'access', 'denied', 'Comprobante de pago ajeno o inexistente rechazado.')
        return render(request, 'error.html', {'title': 'Comprobante no disponible', 'status': 404,
            'message': 'No se encontró un comprobante disponible para esta cuenta.'}, status=404)
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
            record(request, 'profile', 'success', 'Nombres ficticios del perfil actualizados.')
        messages.success(request, 'El perfil de demostración se actualizó correctamente.')
        return redirect('perfil')
    return render(request, 'perfil.html', {'form': form, 'account': account, 'active_page': 'perfil'},
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
                DemoCard.objects.filter(pk=card.pk).update(status=new_status, changed_at=timezone.now())
                record(request, 'card', 'success', 'Tarjeta de prueba ' + ('bloqueada.' if new_status == DemoCard.Status.BLOCKED else 'activada.'))
            messages.success(request, 'El estado de la tarjeta de prueba se actualizó.')
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
    faqs = [
        {'question': '¿Este prototipo utiliza dinero real?', 'answer': 'No. Las cuentas, los saldos, los comercios y los pagos son ficticios y pertenecen al ejercicio académico. No existe conexión con los servicios de Pluxee.'},
        {'question': '¿Qué ocurre si una consulta se interrumpe?', 'answer': 'La consulta queda pendiente y permite reintentar. Una interrupción no cambia el saldo ni se muestra como un saldo cero.'},
        {'question': '¿Cómo funciona el pago de demostración?', 'answer': 'Se selecciona un comercio ficticio, un monto entero en pesos y el PIN de prueba 4826. El sistema valida la cuenta, la tarjeta, los servicios y el saldo antes de crear un cargo y un comprobante.'},
        {'question': '¿Se puede bloquear la tarjeta de prueba?', 'answer': 'La opción Mi tarjeta permite bloquearla y activarla. Mientras está bloqueada no admite pagos académicos, pero permite consultar saldo y movimientos.'},
        {'question': '¿Cuándo finaliza la sesión?', 'answer': 'El acceso finaliza al cerrar la sesión o al alcanzar los límites de inactividad o duración configurados. La navegación activa conserva el acceso mientras la sesión siga vigente.'},
        {'question': '¿Qué información puede editarse?', 'answer': 'Mi perfil permite cambiar únicamente el nombre y el apellido ficticios de esta cuenta. No se requieren datos personales ni credenciales de servicios reales.'},
    ]
    return render(request, 'ayuda.html', {'faqs': faqs, 'account': account, 'active_page': 'ayuda'})
