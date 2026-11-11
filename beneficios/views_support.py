"""Reportes de prueba con lectura separada por perfil."""
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from .forms_support import SupportReportFilterForm, SupportReportForm, SupportReportUpdateForm
from .models import SupportReport
from .security import protected
from .support_history import capture_report, save_report_change


NEXT_STATUS = {
    SupportReport.Status.RECEIVED: SupportReport.Status.REVIEW,
    SupportReport.Status.REVIEW: SupportReport.Status.RESOLVED,
}


@require_http_methods(['GET', 'POST'])
@protected()
def reportar_problema(request):
    if request.user.is_staff:
        return redirect('seguimiento')

    status = 200
    if request.method == 'POST':
        form = SupportReportForm(request.POST)
        if form.is_valid():
            SupportReport.objects.create(reporter=request.user, **form.cleaned_data)
            messages.success(request, 'El reporte quedó registrado. El folio está en Mis reportes.')
            return redirect(reverse('reportar_problema', fragment='mis-reportes'))
        status = 400
    else:
        category = request.GET.get('categoria', '')
        form = SupportReportForm(initial={'category': category if category in SupportReport.Category.values else ''})

    own_reports = SupportReport.objects.filter(reporter=request.user)
    return render(request, 'reportar_problema.html', {
        'form': form,
        'reports': Paginator(own_reports, 8).get_page(request.GET.get('page')),
        'active_page': 'reportar_problema',
    }, status=status)


@require_GET
@protected(administrator=True)
def reportes_admin(request):
    filters = SupportReportFilterForm(request.GET)
    reports = SupportReport.objects.select_related('reporter', 'assigned_to')
    valid_filters = filters.is_valid()
    if valid_filters:
        if filters.cleaned_data['categoria']:
            reports = reports.filter(category=filters.cleaned_data['categoria'])
        if filters.cleaned_data['estado']:
            reports = reports.filter(status=filters.cleaned_data['estado'])
        if filters.cleaned_data['prioridad']:
            reports = reports.filter(priority=filters.cleaned_data['prioridad'])
        responsible = filters.cleaned_data['responsable']
        if responsible == 'none':
            reports = reports.filter(assigned_to__isnull=True)
        elif responsible:
            reports = reports.filter(assigned_to_id=int(responsible))
    else:
        reports = reports.none()
    return render(request, 'reportes_admin.html', {
        'filters': filters,
        'reports': Paginator(reports, 8).get_page(request.GET.get('page')),
        'active_page': 'reportes_admin',
    }, status=200 if valid_filters else 400)


@require_POST
@protected(administrator=True)
def reportes_admin_actualizar(request, report_id):
    form = SupportReportUpdateForm(request.POST)
    with transaction.atomic():
        report = get_object_or_404(SupportReport.objects.select_for_update(), pk=report_id)
        if not form.is_valid():
            messages.error(request, 'Revisa el estado y la extensión de la respuesta antes de guardar.')
        elif NEXT_STATUS.get(report.status) != form.cleaned_data['status']:
            messages.error(request, 'Ese cambio de estado no está disponible. Revisa el estado actual del reporte.')
        else:
            previous = capture_report(report)
            report.status = form.cleaned_data['status']
            fields = ['status']
            if form.cleaned_data['response']:
                report.response = form.cleaned_data['response']
                fields.append('response')
            save_report_change(report, previous, request.user, update_fields=fields)
            messages.success(request, 'El estado del reporte de prueba se actualizó.')

    filters = SupportReportFilterForm(request.GET)
    query = {key: value for key, value in filters.cleaned_data.items() if value} if filters.is_valid() else {}
    try:
        page = int(request.GET.get('page', ''))
    except ValueError:
        page = 1
    if page > 1:
        query['page'] = page
    return redirect(reverse('reportes_admin', query=query, fragment='lista-reportes'))
