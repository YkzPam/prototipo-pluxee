from datetime import datetime, timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from beneficios.models import BenefitAccount, Merchant, Movement, Notification, Payment, ServiceState, SupportReport


class NotificationsAndDetailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username='titular_aviso')
        cls.other = get_user_model().objects.create_user(username='otra_cuenta_aviso')
        cls.account = BenefitAccount.objects.create(user=cls.user, number_suffix='9012')
        cls.merchant = Merchant.objects.create(code='AVISO001', name='Comercio aviso', category='Almacén',
            commune='Santiago', address='Dirección de control', description='Control')
        cls.movement = Movement.objects.create(account=cls.account, kind='cargo', amount=1200,
            description='Compra registrada', occurred_at=timezone.now())
        cls.payment = Payment.objects.create(user=cls.user, account=cls.account, merchant=cls.merchant,
            movement=cls.movement, amount=1200, balance_after=2800, idempotency_key=uuid4(), method='qr')
        ServiceState.objects.create(code='movements', label='Movimientos')

    def test_new_movement_notifies_once_and_rollback_keeps_no_notice(self):
        key = f'movement:{self.movement.pk}'
        self.assertEqual(Notification.objects.filter(source_key=key, user=self.user).count(), 1)
        self.movement.description = 'Descripción corregida'
        self.movement.save(update_fields=['description'])
        self.assertEqual(Notification.objects.filter(source_key=key).count(), 1)
        with self.assertRaises(ValueError):
            with transaction.atomic():
                movement = Movement.objects.create(account=self.account, kind='abono', amount=1000,
                    description='Abono sin confirmar', occurred_at=timezone.now())
                rolled_back_key = f'movement:{movement.pk}'
                raise ValueError('La operación se revierte')
        self.assertFalse(Notification.objects.filter(source_key=rolled_back_key).exists())

    def test_support_response_notice_uses_only_the_fields_saved(self):
        report = SupportReport.objects.create(reporter=self.user, category='other', description='Consulta')
        self.assertFalse(Notification.objects.filter(user=self.user, kind='support').exists())
        report.response = 'Respuesta registrada'
        report.status = 'review'
        report.save(update_fields=['response', 'status'])
        self.assertEqual(Notification.objects.filter(user=self.user, kind='support').count(), 1)
        report.save(update_fields=['response', 'status'])
        self.assertEqual(Notification.objects.filter(user=self.user, kind='support').count(), 1)
        report.response = 'Texto que todavía no se guarda'
        report.save(update_fields=['updated_at'])
        self.assertEqual(Notification.objects.filter(user=self.user, kind='support').count(), 1)

    def test_list_shows_concept_and_amount_grouped_by_day_without_foreign_movements(self):
        other_account = BenefitAccount.objects.create(user=self.other, number_suffix='3344')
        foreign = Movement.objects.create(account=other_account, kind='cargo', amount=9900,
            description='Compra de otra cuenta', occurred_at=timezone.now())
        # Un aviso asignado por error a otra cuenta no debe revelar los datos del movimiento ajeno.
        Notification.objects.filter(source_key=f'movement:{foreign.pk}').update(user=self.user)

        self.client.force_login(self.user)
        response = self.client.get(reverse('notificaciones'))
        self.assertContains(response, '<h3 class="notification-day">Hoy</h3>', html=True)
        self.assertContains(response, 'Compra registrada')
        self.assertContains(response, '$1.200')
        self.assertNotContains(response, 'Compra de otra cuenta')
        self.assertNotContains(response, '9.900')
        notices = {notice.source_key: notice for notice in response.context['notifications']}
        self.assertEqual(notices[f'movement:{self.movement.pk}'].amount, 1200)
        self.assertIsNone(notices[f'movement:{foreign.pk}'].amount)

    def test_read_actions_are_scoped_to_the_current_user(self):
        notice = Notification.objects.get(source_key=f'movement:{self.movement.pk}')
        foreign = Notification.objects.create(user=self.other, kind='credit', source_key='control:otra')
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(reverse('notificacion_leer', args=[foreign.pk])).status_code, 404)
        response = self.client.post(reverse('notificacion_leer', args=[notice.pk]), HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['unread_count'], 0)
        self.client.post(reverse('notificaciones_leer_todas'))
        foreign.refresh_from_db()
        self.assertIsNone(foreign.read_at)
        secured = Client(enforce_csrf_checks=True)
        secured.force_login(self.user)
        self.assertEqual(secured.post(reverse('notificaciones_leer_todas')).status_code, 403)

    def test_detail_is_private_and_links_only_the_owners_receipt(self):
        url = reverse('detalle_movimiento', args=[self.movement.pk])
        self.assertEqual(self.client.get(url).status_code, 401)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.user)
        result = self.client.get(url)
        self.assertEqual(result.status_code, 200)
        data = result.json()['data']
        self.assertEqual(data['amount'], 1200)
        self.assertEqual(data['receipt_url'], reverse('comprobante', args=[self.payment.pk]))
        self.assertEqual(data['pdf_url'], reverse('comprobante_pdf', args=[self.payment.pk]))
        ServiceState.objects.filter(code='movements').update(available=False)
        self.assertEqual(self.client.get(url).status_code, 503)

    def test_summary_filters_month_boundaries_and_returns_selected_week_links(self):
        from beneficios.services import MockDataServiceAdapter
        now = timezone.localtime()
        start = datetime(now.year, now.month, 1, tzinfo=now.tzinfo)
        Movement.objects.create(account=self.account, kind='cargo', amount=800,
            description='Primer día', occurred_at=start)
        Movement.objects.create(account=self.account, kind='cargo', amount=9999,
            description='Mes anterior', occurred_at=start-timedelta(seconds=1))
        adapter = MockDataServiceAdapter()
        summary = adapter.monthly_summary(self.account)
        self.assertEqual(summary['spent'], 2000)
        self.assertEqual(sum(week['amount'] for week in summary['weekly']), summary['spent'])
        self.assertEqual(len(summary['periods']), 6)
        self.client.force_login(self.user)
        response = self.client.get(reverse('api_movimientos', args=[self.account.pk]),
            {'resumen': 'mensual', 'mes': '1900-01'})
        self.assertEqual(response.status_code, 400)
