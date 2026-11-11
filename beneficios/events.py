"""Observer: el evento de dominio notifica al registro sin guardar secretos."""
from dataclasses import dataclass
from logging import getLogger
from django.db import transaction
from .models import AuditEvent

logger = getLogger(__name__)
movement_logger = getLogger('beneficios.movimientos')


def log_committed_movement(movement):
    # Solo referencias internas. Sin nombres, montos, contraseñas ni PIN.
    transaction.on_commit(lambda: movement_logger.info(
        'Movimiento registrado | ID %s | tipo %s', movement.pk, movement.kind,
    ), robust=True)


@dataclass(frozen=True)
class DomainEvent:
    actor: object
    event_type: str
    outcome: str
    detail: str
    request_id: object
    duration_ms: int | None = None
    interruption_id: int | None = None
    target_id: int | None = None


class AuditObserver:
    def update(self, event):
        # Un fallo del observador no debe dejar rota una transacción exterior.
        with transaction.atomic():
            AuditEvent.objects.create(actor=event.actor if getattr(event.actor, 'is_authenticated', False) else None,
                                      event_type=event.event_type, outcome=event.outcome,
                                      detail=event.detail, request_id=event.request_id,
                                      duration_ms=event.duration_ms, interruption_id=event.interruption_id,
                                      target_id=event.target_id)


class EventSubject:
    def __init__(self, observers):
        self.observers = tuple(observers)

    def notify(self, event):
        ok = True
        for observer in self.observers:
            try:
                observer.update(event)
            except Exception:
                # No registrar entradas, cookies o excepciones que puedan incluir secretos.
                logger.error('No fue posible registrar un evento del prototipo.')
                ok = False
        return ok


def record(request, event_type, outcome, detail, duration_ms=None, *, interruption_id=None, target_id=None):
    return EventSubject([AuditObserver()]).notify(DomainEvent(
        actor=request.user, event_type=event_type, outcome=outcome, detail=detail,
        request_id=request.request_id, duration_ms=duration_ms,
        interruption_id=interruption_id, target_id=target_id,
    ))
