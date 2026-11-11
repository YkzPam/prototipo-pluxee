import csv
from datetime import datetime, time, timedelta
from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET

from .charts import bar_chart
from .csv_export import safe_csv_text
from .events import record
from .forms_admin_reports import MovementReportForm
from .models import AuditEvent, Movement
from .security import protected

EXPORT_LIMIT = 10000


def _report_form(parameters):
    values = parameters.copy()
    if 'desde' not in values and 'hasta' not in values:
        today = timezone.localdate()
        values['desde'] = today.replace(day=1).isoformat()
        values['hasta'] = today.isoformat()
    return MovementReportForm(values)


def _movement_query(values):
    zone = timezone.get_current_timezone()
    start = datetime.combine(values['desde'], time.min, tzinfo=zone)
    end = datetime.combine(values['hasta'] + timedelta(days=1), time.min, tzinfo=zone)
    query = Movement.objects.filter(occurred_at__gte=start, occurred_at__lt=end)
    if values['tipo']:
        query = query.filter(kind=values['tipo'])
    if values['usuario']:
        query = query.filter(account__user__username__iexact=values['usuario'])
    return query


def _filter_query(values):
    return urlencode({
        'desde': values['desde'].isoformat(), 'hasta': values['hasta'].isoformat(),
        'tipo': values['tipo'], 'usuario': values['usuario'],
    })


def _report_page(request, form, *, error=None, status=200):
    context = {'active_page': 'admin_informes', 'filters': form, 'report_error': error}
    if form.is_valid():
        query = _movement_query(form.cleaned_data)
        credited, spent = 0, 0
        first_day, last_day = form.cleaned_data['desde'], form.cleaned_data['hasta']
        # Hasta dos meses se agrupa por día; en periodos más largos, por semana.
        bucket_days = 1 if (last_day - first_day).days < 62 else 7
        buckets = (last_day - first_day).days // bucket_days + 1
        daily_credit, daily_spent = [0] * buckets, [0] * buckets
        for occurred_at, kind, amount in query.order_by().values_list('occurred_at', 'kind', 'amount').iterator():
            index = min(buckets - 1, (timezone.localtime(occurred_at).date() - first_day).days // bucket_days)
            if kind == Movement.Kind.CREDIT:
                credited += amount
                daily_credit[index] += amount
            elif kind == Movement.Kind.DEBIT:
                spent += amount
                daily_spent[index] += amount
        labels = [(first_day + timedelta(days=index * bucket_days)).strftime('%d/%m') for index in range(buckets)]
        context['movement_chart'] = bar_chart(
            labels, [('Abonos', 'bar-success', daily_credit), ('Compras', 'bar-purple', daily_spent)], money=True)
        context['chart_bucket'] = 'día' if bucket_days == 1 else 'semana'
        paginator = Paginator(query.select_related('account__user'), 25)
        encoded = _filter_query(form.cleaned_data)
        context.update({
            'valid_filters': True, 'credited': credited, 'spent': spent,
            'record_count': paginator.count,
            'movements': paginator.get_page(request.GET.get('page')),
            'filter_query': encoded,
            'export_url': reverse('admin_informes_exportar') + '?' + encoded,
            'export_limit': EXPORT_LIMIT,
        })
    return render(request, 'admin_informes.html', context, status=status)


@require_GET
@protected(administrator=True)
def admin_informes(request):
    return _report_page(request, _report_form(request.GET))


@require_GET
@protected(administrator=True)
def admin_informes_exportar(request):
    form = _report_form(request.GET)
    if not form.is_valid():
        return _report_page(request, form, status=400)
    values = form.cleaned_data
    rows = list(_movement_query(values).select_related('account__user')[:EXPORT_LIMIT + 1])
    if len(rows) > EXPORT_LIMIT:
        limit_label = f'{EXPORT_LIMIT:,}'.replace(',', '.')
        return _report_page(request, form, error=(
            f'La descarga supera el máximo de {limit_label} movimientos. '
            'Acota el periodo, el tipo o el usuario y vuelve a intentar.'
        ), status=400)
    if not record(request, AuditEvent.Type.ACCESS, AuditEvent.Outcome.SUCCESS,
                  f'Archivo CSV de movimientos generado. Filas {len(rows)}. '
                  f'Periodo {values["desde"].isoformat()} a {values["hasta"].isoformat()}.'):
        return _report_page(request, form,
                            error='No fue posible registrar la descarga en la bitácora. Intenta nuevamente.', status=503)
    filename = f'movimientos_{values["desde"].isoformat()}_{values["hasta"].isoformat()}.csv'
    response = HttpResponse(content_type='text/csv; charset=utf-8',
                            headers={'Content-Disposition': f'attachment; filename="{filename}"'})
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow(['N.º de movimiento', 'Fecha y hora', 'Usuario', 'Tipo', 'Importe (CLP)', 'Descripción'])
    for row in rows:
        writer.writerow((
            row.pk, timezone.localtime(row.occurred_at).isoformat(timespec='seconds'),
            safe_csv_text(row.account.user.username), row.get_kind_display(), row.amount,
            safe_csv_text(row.description),
        ))
    return response
