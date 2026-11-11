"""Avisos persistidos en la transacción del movimiento o la respuesta."""
from hashlib import sha256

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Movement, Notification, SupportReport


@receiver(post_save, sender=Movement, dispatch_uid='beneficios.movement_notification')
def movement_notification(sender, instance, created, raw, using, **kwargs):
    if raw or not created:
        return
    kind = Notification.Kind.CREDIT if instance.kind == Movement.Kind.CREDIT else Notification.Kind.DEBIT
    Notification.objects.using(using).get_or_create(
        source_key=f'movement:{instance.pk}',
        defaults={'user_id': instance.account.user_id, 'kind': kind},
    )


@receiver(pre_save, sender=SupportReport, dispatch_uid='beneficios.support_notification_previous')
def support_previous_state(sender, instance, raw, using, update_fields, **kwargs):
    instance._notification_state = None
    if raw or instance._state.adding:
        return
    if update_fields is not None and not {'response', 'status'}.intersection(update_fields):
        return
    previous = sender.objects.using(using).filter(pk=instance.pk).only('response', 'status').first()
    if previous is None:
        return
    response = instance.response
    status = instance.status
    if update_fields is not None:
        if 'response' not in update_fields:
            response = previous.response
        if 'status' not in update_fields:
            status = previous.status
    response = response.strip()
    if response and (response != previous.response.strip() or status != previous.status):
        instance._notification_state = (status, response)


@receiver(post_save, sender=SupportReport, dispatch_uid='beneficios.support_notification')
def support_notification(sender, instance, created, raw, using, **kwargs):
    state = getattr(instance, '_notification_state', None)
    if raw or created or state is None:
        return
    digest = sha256('\0'.join(state).encode('utf-8')).hexdigest()[:40]
    Notification.objects.using(using).get_or_create(
        source_key=f'support:{instance.pk}:{digest}',
        defaults={'user_id': instance.reporter_id, 'kind': Notification.Kind.SUPPORT},
    )
