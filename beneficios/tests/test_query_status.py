from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import DatabaseError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from beneficios.models import AuditEvent, BenefitAccount, ServiceState


class QueryStatusTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.admin = users.create_user(username='admin.estado', is_staff=True)
        cls.beneficiary = users.create_user(username='beneficiario.estado')
        cls.temporary_user = users.create_user(username='usuario.temporal', must_change_password=True)
        BenefitAccount.objects.create(user=cls.beneficiary, number_suffix='6789')
        ServiceState.objects.create(code='movements', label='Movimientos')
        ServiceState.objects.create(code='balance', label='Saldo')

    def test_home_and_endpoint_reflect_administrator_interruptions_and_recovery(self):
        self.client.force_login(self.beneficiary)
        admin = Client()
        admin.force_login(self.admin)
        controls_url = reverse('servicios')

        for changes, expected, notice in (
            ([], [], ''),
            ([('movements', 'unavailable'), ('balance', 'unavailable')], ['balance', 'movements'],
             'Hay una interrupción simulada en las consultas de saldo y movimientos.'),
            ([('balance', 'available')], ['movements'], 'Hay una interrupción simulada en la consulta de movimientos.'),
            ([('movements', 'available')], [], ''),
        ):
            with self.subTest(interrupted=expected):
                for service, state in changes:
                    result = admin.post(controls_url, {'service': service, 'state': state})
                    self.assertRedirects(result, reverse('seguimiento'), fetch_redirect_response=False)

                events_before = AuditEvent.objects.count()
                home = self.client.get(reverse('inicio'))
                self.assertContains(home, f'<p data-query-status-message>{notice}</p>', html=True)
                self.assertEqual(home.context['interrupted_queries'], expected)
                result = self.client.get(reverse('estado_consultas'))
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.json()['status'], 'updated')
                self.assertEqual(result.json()['data'], {'interrupted': expected})
                self.assertEqual(AuditEvent.objects.count(), events_before)

    def test_status_endpoint_requires_authentication_and_permits_only_get(self):
        url = reverse('estado_consultas')
        self.assertEqual(self.client.get(url).status_code, 401)

        self.client.force_login(self.temporary_user)
        blocked = self.client.get(url)
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(blocked.json()['status'], 'password_change_required')

        self.client.force_login(self.beneficiary)
        self.assertEqual(self.client.post(url).status_code, 405)

    @override_settings(SESSION_IDLE_SECONDS=60, SESSION_MAX_SECONDS=300)
    def test_passive_status_requests_do_not_delay_session_expiry(self):
        self.client.force_login(self.beneficiary)
        url = reverse('estado_consultas')
        now = timezone.now()
        session = self.client.session
        last_activity = (now - timedelta(seconds=settings.SESSION_IDLE_SECONDS - 10)).timestamp()
        session['auth_started_at'] = last_activity
        session['last_activity_at'] = last_activity
        session.save()

        with patch('django.utils.timezone.now', return_value=now):
            self.assertEqual(self.client.get(url).status_code, 200)
            self.assertEqual(self.client.session['last_activity_at'], last_activity)

        with patch('django.utils.timezone.now', return_value=now + timedelta(seconds=11)):
            result = self.client.get(url)
            self.assertEqual(result.status_code, 401)
            self.assertEqual(result.json()['status'], 'expired')
            self.assertEqual(AuditEvent.objects.filter(event_type=AuditEvent.Type.EXPIRED).count(), 1)

    def test_status_read_failure_leaves_home_available_without_asserting_service_availability(self):
        self.client.force_login(self.beneficiary)
        with patch.object(ServiceState.objects, 'using', side_effect=DatabaseError('Lectura de prueba fallida')):
            home = self.client.get(reverse('inicio'))
            self.assertEqual(home.status_code, 200)
            self.assertFalse(home.context['interrupted_queries'])
            result = self.client.get(reverse('estado_consultas'))
            self.assertEqual(result.status_code, 503)
            self.assertEqual(result.json()['status'], 'pending')
            self.assertNotIn('data', result.json())
