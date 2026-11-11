"""Parámetros del sistema que administración puede ajustar; cada cambio queda en la bitácora."""
from django import forms
from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from . import parameters
from .events import record
from .models import AuditEvent, SystemParameters
from .security import protected
from .templatetags.moneda import clp

LABELS = {
    'registration_initial_credit': 'Abono inicial de registro',
    'login_max_attempts': 'Intentos de ingreso antes del bloqueo',
    'session_idle_minutes': 'Minutos de inactividad de la sesión',
    'payment_max_amount': 'Monto máximo por compra',
}
HELP = {
    'registration_initial_credit': 'Monto en pesos que recibe cada cuenta nueva. Con $0 no se registra abono.',
    'login_max_attempts': 'Intentos fallidos por cuenta antes del bloqueo temporal de 15 minutos.',
    'session_idle_minutes': 'Tiempo sin actividad tras el cual la sesión se cierra. Aplica desde la siguiente solicitud.',
    'payment_max_amount': 'Límite por compra que se valida en el servidor al revisar un pago.',
}
# Nombres breves para que el detalle de la bitácora (180 caracteres) admita los cuatro cambios.
AUDIT_LABELS = {
    'registration_initial_credit': 'Abono inicial',
    'login_max_attempts': 'Intentos de ingreso',
    'session_idle_minutes': 'Inactividad (min)',
    'payment_max_amount': 'Máximo por compra',
}
MONEY = {'registration_initial_credit', 'payment_max_amount'}


class ParametersForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, (minimum, maximum) in parameters.LIMITS.items():
            self.fields[name] = forms.IntegerField(
                label=LABELS[name], min_value=minimum, max_value=maximum,
                help_text=f'{HELP[name]} Rango permitido: {_value(name, minimum)} a {_value(name, maximum)}.',
                widget=forms.NumberInput(attrs={'min': minimum, 'max': maximum, 'step': 1, 'inputmode': 'numeric'}),
            )


def _value(name, value):
    return f'${clp(value)}' if name in MONEY else str(value)


@require_http_methods(['GET', 'POST'])
@protected(administrator=True)
def admin_parametros(request):
    active = parameters.current()
    initial = {name: getattr(active, name) for name in parameters.LIMITS}
    form = ParametersForm(request.POST if request.method == 'POST' else None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        changes = [f'{AUDIT_LABELS[name]}: de {_value(name, initial[name])} a {_value(name, value)}'
                   for name, value in form.cleaned_data.items() if value != initial[name]]
        if not changes:
            messages.info(request, 'Los parámetros no tenían cambios.')
            return redirect('admin_parametros')
        with transaction.atomic():
            SystemParameters.objects.update_or_create(
                pk=SystemParameters.SINGLETON_ID, defaults={**form.cleaned_data, 'updated_by': request.user})
            if not record(request, AuditEvent.Type.SETTINGS, AuditEvent.Outcome.SUCCESS, '; '.join(changes)[:180]):
                transaction.set_rollback(True)
                messages.error(request, 'La bitácora no pudo registrar el cambio. No se modificaron los parámetros.')
                return redirect('admin_parametros')
        messages.success(request, 'Se actualizaron los parámetros del sistema.')
        return redirect('admin_parametros')
    history = AuditEvent.objects.filter(event_type=AuditEvent.Type.SETTINGS).select_related('actor')[:5]
    return render(request, 'admin_parametros.html', {
        'form': form, 'active': active, 'history': history, 'active_page': 'admin_parametros',
    }, status=400 if form.is_bound and not form.is_valid() else 200)
