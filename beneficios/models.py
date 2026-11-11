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
    credit_reference = models.UUIDField(null=True, blank=True, unique=True, editable=False)

    class Meta:
        ordering = ['-occurred_at', '-pk']


SERVICE_CODES = [('balance', 'Saldo'), ('movements', 'Movimientos')]


class ServiceInterruption(models.Model):
    """Periodo de indisponibilidad inducido desde el panel de demostración."""

    service_code = models.CharField(max_length=20, choices=SERVICE_CODES)
    started_at = models.DateTimeField(db_index=True)
    restored_at = models.DateTimeField(null=True, blank=True)
    verification_note = EncryptedCharField(max_length=400, null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)


class SupportReport(models.Model):
    class Priority(models.TextChoices):
        LOW = 'low', 'Baja'
        NORMAL = 'normal', 'Normal'
        HIGH = 'high', 'Alta'
        URGENT = 'urgent', 'Urgente'

    class Category(models.TextChoices):
        BALANCE = 'balance', 'Consulta de saldo'
        MOVEMENTS = 'movements', 'Consulta de movimientos'
        SESSION = 'session', 'Cierre de sesión'
        OTHER = 'other', 'Otro problema'

    class Status(models.TextChoices):
        RECEIVED = 'received', 'Recibido'
        REVIEW = 'review', 'En revisión'
        RESOLVED = 'resolved', 'Resuelto'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    category = models.CharField(max_length=12, choices=Category.choices)
    description = EncryptedCharField(max_length=360)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.RECEIVED)
    priority = models.CharField(max_length=8, choices=Priority.choices, default=Priority.NORMAL)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name='assigned_support_reports')
    response = EncryptedCharField(max_length=400, default='', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-pk']


class SupportReportUpdate(models.Model):
    report = models.ForeignKey(SupportReport, on_delete=models.CASCADE, related_name='updates')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                              related_name='support_report_updates')
    old_status = models.CharField(max_length=12, choices=SupportReport.Status.choices)
    new_status = models.CharField(max_length=12, choices=SupportReport.Status.choices)
    old_priority = models.CharField(max_length=8, choices=SupportReport.Priority.choices)
    new_priority = models.CharField(max_length=8, choices=SupportReport.Priority.choices)
    old_assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+')
    new_assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+')
    response_changed = models.BooleanField(default=False)
    response = EncryptedCharField(max_length=400, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']


class ServiceState(models.Model):
    code = models.CharField(max_length=20, unique=True, choices=SERVICE_CODES)
    label = models.CharField(max_length=40)
    available = models.BooleanField(default=True)
    changed_at = models.DateTimeField(auto_now=True)
    active_interruption = models.ForeignKey(ServiceInterruption, null=True, blank=True, on_delete=models.PROTECT)


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
        CARD = 'card', 'Estado de tarjeta'
        PROFILE = 'profile', 'Perfil de usuario'
        SETTINGS = 'settings', 'Parámetros del sistema'

    class Outcome(models.TextChoices):
        SUCCESS = 'success', 'Correcto'
        PENDING = 'pending', 'Pendiente'
        DENIED = 'denied', 'Rechazado'
        EXPIRED = 'expired', 'Vencida'

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    target = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='targeted_audit_events',
    )
    event_type = models.CharField(max_length=20, choices=Type.choices)
    outcome = models.CharField(max_length=12, choices=Outcome.choices)
    detail = models.CharField(max_length=180)
    request_id = models.UUIDField(db_index=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    interruption = models.ForeignKey(
        ServiceInterruption, null=True, blank=True, on_delete=models.PROTECT, related_name='pending_queries',
    )

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
    dynamic_code_digest = models.CharField(max_length=64, blank=True, default='', db_default='')
    dynamic_expires_at = models.DateTimeField(null=True, blank=True)

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
    class Method(models.TextChoices):
        ONLINE = 'online', 'Pago online'
        QR = 'qr', 'Pago QR'
        DYNAMIC = 'dynamic', 'Clave dinámica'
        CARD = 'card', 'Tarjeta física o virtual'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='demo_payments')
    account = models.ForeignKey(BenefitAccount, on_delete=models.PROTECT, related_name='payments')
    merchant = models.ForeignKey(Merchant, on_delete=models.PROTECT, related_name='payments')
    movement = models.OneToOneField(Movement, on_delete=models.PROTECT, related_name='payment')
    amount = EncryptedIntegerField(min_value=1)
    balance_after = EncryptedIntegerField()
    idempotency_key = models.UUIDField()
    method = models.CharField(max_length=8, choices=Method.choices, default=Method.ONLINE, db_default=Method.ONLINE)
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


class Notification(models.Model):
    class Kind(models.TextChoices):
        CREDIT = 'credit', 'Abono'
        DEBIT = 'debit', 'Compra'
        SUPPORT = 'support', 'Respuesta a reporte'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    kind = models.CharField(max_length=16, choices=Kind.choices)
    source_key = models.CharField(max_length=110, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        indexes = [models.Index(fields=['user', 'read_at'], name='notification_user_read_idx')]

    @property
    def title(self):
        return {
            self.Kind.CREDIT: 'Abono registrado',
            self.Kind.DEBIT: 'Compra registrada',
            self.Kind.SUPPORT: 'Actualización de tu reporte',
        }.get(self.kind, 'Notificación de tu cuenta')

    @property
    def body(self):
        return {
            self.Kind.CREDIT: 'Hay un nuevo abono en el historial de tu cuenta.',
            self.Kind.DEBIT: 'El cargo de una compra quedó registrado en tu historial.',
            self.Kind.SUPPORT: 'Administración actualizó tu reporte y hay una respuesta disponible.',
        }.get(self.kind, 'Hay una actualización disponible para consultar.')

    @property
    def destination(self):
        from django.urls import reverse
        if self.kind == self.Kind.SUPPORT:
            return reverse('reportar_problema') + '#mis-reportes'
        return reverse('movimientos')


class SystemParameters(models.Model):
    """Fila única con los parámetros que administración puede ajustar sin reiniciar el servidor."""
    SINGLETON_ID = 1

    # Clave explícita sin autoincremento: MySQL no admite restricciones CHECK sobre columnas autoincrementales.
    id = models.PositiveSmallIntegerField(primary_key=True, default=SINGLETON_ID, editable=False)
    registration_initial_credit = models.PositiveIntegerField()
    login_max_attempts = models.PositiveSmallIntegerField()
    session_idle_minutes = models.PositiveSmallIntegerField()
    payment_max_amount = models.PositiveIntegerField()
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name='+')

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name='system_parameters_single_row')]


class MerchantCategory(models.Model):
    """Categorías que administración puede asignar a un comercio."""
    name = models.CharField(max_length=40, unique=True)
    position = models.PositiveSmallIntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['position', 'name']

    def __str__(self):
        return self.name


class HelpTopic(models.Model):
    """Pregunta frecuente que se muestra en Ayuda."""
    question = models.CharField(max_length=160)
    answer = models.TextField(max_length=800)
    position = models.PositiveSmallIntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['position', 'pk']
