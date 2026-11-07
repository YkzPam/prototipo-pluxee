from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from beneficios.models import AuditEvent, BenefitAccount, ServiceInterruption, ServiceState


class InterruptionHistoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.admin = users.create_user(username='admin.interrupciones', is_staff=True)
        cls.beneficiary = users.create_user(username='beneficiario.interrupciones')
        cls.account = BenefitAccount.objects.create(user=cls.beneficiary, number_suffix='1005')
        ServiceState.objects.create(code='balance', label='Saldo')
        ServiceState.objects.create(code='movements', label='Movimientos')

    def set_state(self, client, code, state):
        return client.post(reverse('servicios'), {'service': code, 'state': state})

    def test_history_records_distinct_periods_and_counts_only_the_affected_queries(self):
        admin = Client()
        beneficiary = Client()
        admin.force_login(self.admin)
        beneficiary.force_login(self.beneficiary)
        balance = reverse('api_saldo', args=[self.account.pk])
        movements = reverse('api_movimientos', args=[self.account.pk])
        start = timezone.now().replace(microsecond=0)

        with patch('django.utils.timezone.now', return_value=start):
            self.assertEqual(self.set_state(admin, 'balance', 'unavailable').status_code, 302)
            self.assertEqual(self.set_state(admin, 'balance', 'unavailable').status_code, 302)
            self.assertEqual(ServiceInterruption.objects.count(), 1)
            self.assertEqual(beneficiary.get(balance).status_code, 503)
            self.assertEqual(beneficiary.get(balance).status_code, 429)
            self.assertEqual(beneficiary.get(movements).status_code, 200)
            first = ServiceInterruption.objects.get()
            self.assertEqual(first.started_at, start)
            self.assertIsNone(first.restored_at)
            self.assertContains(admin.get(reverse('seguimiento')), 'En curso')

        restored = start + timedelta(seconds=65)
        with patch('django.utils.timezone.now', return_value=restored):
            self.assertEqual(self.set_state(admin, 'balance', 'available').status_code, 302)
            self.assertEqual(beneficiary.get(balance).status_code, 200)
            self.assertEqual(self.set_state(admin, 'movements', 'unavailable').status_code, 302)
            self.assertEqual(beneficiary.get(movements).status_code, 503)
            self.assertEqual(self.set_state(admin, 'balance', 'unavailable').status_code, 302)
            result = admin.get(reverse('seguimiento'))

        self.assertContains(result, 'Historial de interrupciones simuladas')
        periods = {period.pk: period for period in result.context['interruptions']}
        self.assertEqual(len(periods), 3)
        self.assertEqual(periods[first.pk].restored_at, restored)
        self.assertEqual(periods[first.pk].elapsed, '00:01:05')
        self.assertEqual(periods[first.pk].pending_count, 1)
        open_counts = {p.service_code: p.pending_count for p in periods.values() if p.restored_at is None}
        self.assertEqual(open_counts, {'balance': 0, 'movements': 1})
        self.assertEqual(AuditEvent.objects.filter(interruption__isnull=False).count(), 2)

    def test_history_and_simulation_require_an_administrator(self):
        self.client.force_login(self.beneficiary)
        self.assertEqual(self.client.get(reverse('seguimiento')).status_code, 403)
        self.assertEqual(self.set_state(self.client, 'balance', 'unavailable').status_code, 403)
        self.assertFalse(ServiceInterruption.objects.exists())
