"""Parámetros vigentes: la fila guardada por administración o, si aún no existe, la configuración del despliegue."""
from dataclasses import dataclass

from django.conf import settings

from .models import SystemParameters

PAYMENT_MAX_AMOUNT = 1_000_000

# (mínimo, máximo) que acepta el formulario de administración.
LIMITS = {
    'registration_initial_credit': (0, 200_000),
    'login_max_attempts': (3, 10),
    'session_idle_minutes': (5, 60),
    'payment_max_amount': (1_000, PAYMENT_MAX_AMOUNT),
}


@dataclass(frozen=True)
class Parameters:
    registration_initial_credit: int
    login_max_attempts: int
    session_idle_seconds: int
    payment_max_amount: int
    updated_at: object = None
    updated_by: object = None

    @property
    def session_idle_minutes(self):
        return self.session_idle_seconds // 60


def current():
    row = SystemParameters.objects.select_related('updated_by').filter(pk=SystemParameters.SINGLETON_ID).first()
    if row is None:
        return Parameters(
            registration_initial_credit=settings.REGISTRATION_INITIAL_CREDIT,
            login_max_attempts=settings.LOGIN_MAX_ATTEMPTS,
            session_idle_seconds=settings.SESSION_IDLE_SECONDS,
            payment_max_amount=PAYMENT_MAX_AMOUNT,
        )
    return Parameters(
        registration_initial_credit=row.registration_initial_credit, login_max_attempts=row.login_max_attempts,
        session_idle_seconds=row.session_idle_minutes * 60, payment_max_amount=row.payment_max_amount,
        updated_at=row.updated_at, updated_by=row.updated_by,
    )
