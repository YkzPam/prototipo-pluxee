from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from .events import record
from .forms_admin_merchants import MerchantFilterForm, MerchantForm, MerchantStateForm
from .models import AuditEvent, Merchant
from .security import protected
from django.core.paginator import Paginator


class MerchantAuditUnavailable(Exception):
    pass


def _audit(request, detail):
    if not record(request, AuditEvent.Type.ACCESS, AuditEvent.Outcome.SUCCESS, detail):
        raise MerchantAuditUnavailable


@require_GET
@protected(administrator=True)
def admin_comercios(request):
    merchants = Merchant.objects.order_by('name', 'pk')
    filters = MerchantFilterForm(request.GET)
    if filters.is_valid():
        query, state = filters.cleaned_data['q'], filters.cleaned_data['estado']
        if query:
            merchants = merchants.filter(Q(name__icontains=query) | Q(code__icontains=query) | Q(commune__icontains=query))
        if state:
            merchants = merchants.filter(active=state == 'active')
    parameters = request.GET.copy()
    parameters.pop('page', None)
    return render(request, 'admin_comercios.html', {
        'active_page': 'admin_comercios', 'filters': filters,
        'merchants': Paginator(merchants, 15).get_page(request.GET.get('page')),
        'filter_query': parameters.urlencode(),
    })


@require_http_methods(['GET', 'POST'])
@protected(administrator=True)
def admin_comercio_crear(request):
    form = MerchantForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                merchant = form.save()
                _audit(request, f'Comercio creado en el catálogo. Código {merchant.code}.')
        except IntegrityError:
            if not Merchant.objects.filter(code__iexact=form.cleaned_data['code']).exists():
                raise
            form.add_error('code', 'Ese código ya corresponde a otro comercio.')
        except MerchantAuditUnavailable:
            form.add_error(None, 'No fue posible registrar el alta en la bitácora. Intenta nuevamente.')
        else:
            messages.success(request, 'Se creó el comercio y quedó disponible en el catálogo.')
            return redirect('admin_comercio', merchant_id=merchant.pk)
    return render(request, 'admin_comercio.html', {
        'active_page': 'admin_comercios', 'form': form, 'creating': True,
    })


@require_http_methods(['GET', 'POST'])
@protected(administrator=True)
def admin_comercio(request, merchant_id):
    merchant = get_object_or_404(Merchant, pk=merchant_id)
    action = request.POST.get('action') if request.method == 'POST' else None
    form = MerchantForm(request.POST if action == 'edit' else None, instance=merchant)
    state = MerchantStateForm(request.POST if action == 'state' else None, initial={
        'state': 'inactive' if merchant.active else 'active',
    })
    if request.method == 'POST':
        selected = form if action == 'edit' else state if action == 'state' else None
        if selected is None:
            messages.error(request, 'La acción solicitada no está disponible.')
        elif selected.is_valid():
            try:
                with transaction.atomic():
                    locked = get_object_or_404(Merchant.objects.select_for_update(), pk=merchant.pk)
                    if action == 'edit':
                        for field in ('name', 'category', 'commune', 'address', 'description'):
                            setattr(locked, field, form.cleaned_data[field])
                        locked.save(update_fields=['name', 'category', 'commune', 'address', 'description'])
                        _audit(request, f'Datos de comercio actualizados. Código {locked.code}.')
                        result = 'Se guardaron los datos del comercio.'
                    else:
                        active = state.cleaned_data['state'] == 'active'
                        if not active and request.POST.get('confirm_state') != '1':
                            state.add_error(None, 'Confirma la desactivación del comercio para continuar.')
                        elif active != locked.active:
                            locked.active = active
                            locked.save(update_fields=['active'])
                            _audit(request, f'Comercio {"activado" if active else "desactivado"}. Código {locked.code}.')
                        result = 'Se activó el comercio.' if active else 'Se desactivó el comercio.'
            except MerchantAuditUnavailable:
                selected.add_error(None, 'No fue posible registrar el cambio en la bitácora. Intenta nuevamente.')
            else:
                if not selected.errors:
                    messages.success(request, result)
                    return redirect('admin_comercio', merchant_id=merchant.pk)
    return render(request, 'admin_comercio.html', {
        'active_page': 'admin_comercios', 'form': form, 'merchant': merchant, 'state_form': state,
    })
