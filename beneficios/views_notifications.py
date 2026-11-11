from datetime import timedelta

from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.formats import date_format
from django.views.decorators.http import require_GET, require_POST

from .models import Movement, Notification
from .security import protected


def _day_label(moment, today):
    day = timezone.localtime(moment).date()
    if day == today:
        return 'Hoy'
    if day == today - timedelta(days=1):
        return 'Ayer'
    return date_format(day, 'j \\d\\e F')


def _with_movement_detail(request, notifications):
    """Agrega el comercio o concepto y el monto, leyendo solo movimientos de la propia cuenta."""
    movement_ids = {}
    for notification in notifications:
        source, _, value = notification.source_key.partition(':')
        if source == 'movement' and value.isdecimal():
            movement_ids[notification.pk] = int(value)
    movements = Movement.objects.filter(pk__in=movement_ids.values(), account__user=request.user).in_bulk()
    today = timezone.localdate()
    for notification in notifications:
        notification.day_label = _day_label(notification.created_at, today)
        movement = movements.get(movement_ids.get(notification.pk))
        notification.concept = movement.description if movement else ''
        notification.amount = movement.amount if movement else None
    return notifications


@require_GET
@protected()
def notificaciones(request):
    own_notifications = Notification.objects.filter(user=request.user)
    page = Paginator(own_notifications, 15).get_page(request.GET.get('page'))
    page.object_list = _with_movement_detail(request, list(page.object_list))
    return render(request, 'notificaciones.html', {
        'active_page': 'notificaciones',
        'notifications': page,
    })


def _read_result(request):
    if 'application/json' in request.headers.get('Accept', ''):
        count = Notification.objects.filter(user=request.user, read_at__isnull=True).count()
        return JsonResponse({'unread_count': count})
    return redirect('notificaciones')


@require_POST
@protected()
def notificacion_leer(request, notification_id):
    notification = get_object_or_404(Notification, pk=notification_id, user=request.user)
    Notification.objects.filter(pk=notification.pk, user=request.user, read_at__isnull=True).update(read_at=timezone.now())
    return _read_result(request)


@require_POST
@protected()
def notificaciones_leer_todas(request):
    Notification.objects.filter(user=request.user, read_at__isnull=True).update(read_at=timezone.now())
    return _read_result(request)
