from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms_admin_incidents import IncidentManagementForm
from .models import SupportReport
from .security import protected
from .support_history import capture_report, save_report_change


@require_http_methods(['GET', 'POST'])
@protected(administrator=True)
def incidencia_admin(request, report_id):
    with transaction.atomic():
        query = SupportReport.objects
        if request.method == 'POST':
            query = query.select_for_update()
        report = get_object_or_404(query, pk=report_id)
        form = IncidentManagementForm(
            request.POST if request.method == 'POST' else None, report=report,
            initial={'status': report.status, 'priority': report.priority,
                     'assigned_to': report.assigned_to_id, 'response': report.response},
        )
        if request.method == 'POST' and form.is_valid():
            previous = capture_report(report)
            for name in ('status', 'priority', 'assigned_to', 'response'):
                setattr(report, name, form.cleaned_data[name])
            changed = save_report_change(report, previous, request.user,
                                         update_fields=['status', 'priority', 'assigned_to', 'response'])
            messages.success(request, 'Se guardaron los cambios de la incidencia.' if changed
                             else 'La incidencia ya contiene estos datos.')
            return redirect('incidencia_admin', report_id=report.pk)

    history = report.updates.select_related('actor', 'old_assigned_to', 'new_assigned_to')
    return render(request, 'incidencia_admin.html', {
        'active_page': 'reportes_admin', 'report': report, 'form': form,
        'history': Paginator(history, 12).get_page(request.GET.get('page')),
    }, status=400 if request.method == 'POST' else 200)
