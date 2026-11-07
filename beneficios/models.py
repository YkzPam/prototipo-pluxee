import uuid
from django.conf import settings
from django.db import models

from config.encrypted_fields import EncryptedCharField, EncryptedIntegerField


class BenefitAccount(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='benefit_account')
    public_label = models.CharField(max_length=80, default='Beneficio de alimentación')
    number_suffix = EncryptedCharField(max_length=4)
    created_at = models.DateTimeField(auto_now_add=True)


class Movement(models.Model):
    class Kind(models.TextChoices):
        CREDIT = 'abono', 'Abono'
        DEBIT = 'cargo', 'Compra'

    account = models.ForeignKey(BenefitAccount, on_delete=models.PROTECT, related_name='movements')
    kind = models.CharField(max_length=8, choices=Kind.choices)
    amount = EncryptedIntegerField(min_value=1)
    description = EncryptedCharField(max_length=120)
    occurred_at = models.DateTimeField()

    class Meta:
        ordering = ['-occurred_at', '-pk']


class ServiceState(models.Model):
    code = models.CharField(max_length=20, unique=True, choices=[('balance', 'Saldo'), ('movements', 'Movimientos')])
    label = models.CharField(max_length=40)
    available = models.BooleanField(default=True)
    changed_at = models.DateTimeField(auto_now=True)


class AuditEvent(models.Model):
    class Type(models.TextChoices):
        LOGIN = 'login', 'Inicio de sesión'
        LOGOUT = 'logout', 'Cierre de sesión'
        EXPIRED = 'expired', 'Sesión vencida'
        BALANCE = 'balance', 'Consulta de saldo'
        MOVEMENTS = 'movements', 'Consulta de movimientos'
        ACCESS = 'access', 'Control de acceso'
        SERVICE = 'service', 'Escenario de consulta'
        PASSWORD = 'password', 'Cambio de contraseña'
        PAYMENT = 'payment', 'Pago académico'
        CARD = 'card', 'Estado de tarjeta de prueba'
        PROFILE = 'profile', 'Perfil de prueba'

    class Outcome(models.TextChoices):
        SUCCESS = 'success', 'Correcto'
        PENDING = 'pending', 'Pendiente'
        DENIED = 'denied', 'Rechazado'
        EXPIRED = 'expired', 'Vencida'

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    event_type = models.CharField(max_length=20, choices=Type.choices)
    outcome = models.CharField(max_length=12, choices=Outcome.choices)
    detail = models.CharField(max_length=180)
    request_id = models.UUIDField(db_index=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at', '-pk']


class LoginThrottle(models.Model):
    # HMAC de usuario o IP; no contiene contraseñas ni cookies.
    key = models.CharField(max_length=64, unique=True)
    failures = models.PositiveIntegerField(default=0)
    window_started = models.DateTimeField()
    blocked_until = models.DateTimeField(null=True, blank=True)


class Merchant(models.Model):
    """Catálogo persistido de comercios inventados para el ejercicio."""
    code = models.CharField(max_length=12, unique=True)
    name = models.CharField(max_length=80)
    category = models.CharField(max_length=40)
    commune = models.CharField(max_length=40)
    address = models.CharField(max_length=140)
    description = models.CharField(max_length=180)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name', 'pk']

    def __str__(self):
        return f'{self.name} ({self.code})'


class MerchantFavorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='merchant_favorites')
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name='favorites')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'merchant'], name='favorite_user_merchant_unique')]


class DemoCard(models.Model):
    """Tarjeta académica sin PAN, datos bancarios ni conexión externa."""
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Activa'
        BLOCKED = 'blocked', 'Bloqueada'

    account = models.OneToOneField(BenefitAccount, on_delete=models.PROTECT, related_name='demo_card')
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.ACTIVE)
    pin_hash = EncryptedCharField(max_length=128)
    changed_at = models.DateTimeField(auto_now=True)

    @property
    def is_blocked(self):
        return self.status == self.Status.BLOCKED

    @property
    def label(self):
        return self.account.public_label

    @property
    def suffix(self):
        return self.account.number_suffix

    def check_pin(self, raw_pin):
        from django.contrib.auth.hashers import check_password
        return check_password(raw_pin, self.pin_hash)


class Payment(models.Model):
    """Comprobante persistido; cada pago académico corresponde a un único cargo."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='demo_payments')
    account = models.ForeignKey(BenefitAccount, on_delete=models.PROTECT, related_name='payments')
    merchant = models.ForeignKey(Merchant, on_delete=models.PROTECT, related_name='payments')
    movement = models.OneToOneField(Movement, on_delete=models.PROTECT, related_name='payment')
    amount = EncryptedIntegerField(min_value=1)
    balance_after = EncryptedIntegerField()
    idempotency_key = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'idempotency_key'], name='payment_user_key_unique'),
        ]


class PaymentThrottle(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payment_throttle')
    failures = models.PositiveIntegerField(default=0)
    window_started = models.DateTimeField()
    blocked_until = models.DateTimeField(null=True, blank=True)
