from django import forms
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .events import record
from .models import AuditEvent, ServiceInterruption
from .security import protected


class VerificationNoteForm(forms.Form):
    verification_note = forms.CharField(max_length=400)


@require_POST
@protected(administrator=True)
@transaction.atomic
def interrupcion_verificar(request, interruption_id):
    interruption = get_object_or_404(ServiceInterruption.objects.select_for_update(), pk=interruption_id)
    detail_url = f"{reverse('seguimiento')}?interruption={interruption.pk}"
    form = VerificationNoteForm(request.POST)

    if interruption.restored_at is None:
        messages.error(request, 'El servicio debe estar restablecido antes de registrar la comprobación.')
    elif interruption.verified_at is not None:
        messages.error(request, 'Esta interrupción ya tiene una comprobación registrada.')
    elif not form.is_valid():
        messages.error(request, 'La nota debe contener entre 1 y 400 caracteres válidos.')
    else:
        interruption.verification_note = form.cleaned_data['verification_note']
        interruption.verified_at = timezone.now()
        interruption.verified_by = request.user
        interruption.save(update_fields=['verification_note', 'verified_at', 'verified_by'])
        if record(request, AuditEvent.Type.SERVICE, AuditEvent.Outcome.SUCCESS,
                  f'Comprobación registrada tras restablecer la interrupción de prueba {interruption.pk}.'):
            messages.success(request, 'La comprobación del restablecimiento quedó registrada.')
            return redirect(f'{detail_url}#comprobacion-restablecimiento')
        transaction.set_rollback(True)
        messages.error(request, 'La bitácora no pudo registrar la comprobación. Se puede volver a intentar.')

    return redirect(detail_url)
