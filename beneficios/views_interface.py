"""Detalle de lectura para el panel de movimientos de la propia cuenta."""
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET

from .events import record
from .models import Movement, Payment
from .responses import PendingResponseCreator, RejectedResponseCreator, UpdatedResponseCreator
from .security import protected
from .services import MockDataServiceAdapter, SourceUnavailable


@require_GET
@protected(api=True)
def detalle_movimiento(request, movement_id):
    movement = Movement.objects.select_related('account').filter(
        pk=movement_id, account__user=request.user,
    ).first()
    if movement is None:
        record(request, 'access', 'denied', 'Detalle de movimiento ajeno o inexistente rechazado.')
        return RejectedResponseCreator().create_response(request, 'El movimiento no está disponible.', http_status=404)
    try:
        MockDataServiceAdapter.check_service('movements', database='default')
    except SourceUnavailable:
        return PendingResponseCreator().create_response(request, 'La consulta está pendiente. Reintenta cuando vuelva el servicio.')
    payment = Payment.objects.select_related('merchant').filter(
        movement=movement, user=request.user, account_id=movement.account_id,
    ).first()
    data = {
        'id': movement.pk, 'kind': movement.kind, 'type': movement.get_kind_display(),
        'description': movement.description, 'amount': movement.amount,
        'date': timezone.localtime(movement.occurred_at).isoformat(),
        'account_suffix': movement.account.number_suffix,
        'merchant': payment.merchant.name if payment else None,
        'receipt_url': reverse('comprobante', args=[payment.pk]) if payment else None,
        'pdf_url': reverse('comprobante_pdf', args=[payment.pk]) if payment else None,
    }
    return UpdatedResponseCreator().create_response(request, data=data)


@require_GET
@protected()
def apariencia(request):
    return render(request, 'apariencia.html', {
        'active_page': 'apariencia', 'avatar_initial': (
            request.user.get_short_name() or request.user.username
        )[:1].upper(),
    })
