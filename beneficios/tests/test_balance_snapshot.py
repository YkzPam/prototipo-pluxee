from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from beneficios.models import BenefitAccount, Movement, ServiceState


class BalanceSnapshotTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.user = user_model.objects.create_user(username='beneficio')
        cls.account = BenefitAccount.objects.create(user=cls.user, number_suffix='4321')
        other = user_model.objects.create_user(username='otra.cuenta')
        cls.other_account = BenefitAccount.objects.create(user=other, number_suffix='3210')
        Movement.objects.create(account=cls.account, kind='abono', amount=8000,
                                description='Abono de prueba', occurred_at=timezone.now())
        ServiceState.objects.create(code='balance', label='Saldo', available=True)

    def setUp(self):
        self.client.force_login(self.user)
        self.balance_url = reverse('api_saldo', args=[self.account.pk])

    def interrupt(self):
        ServiceState.objects.filter(code='balance').update(available=False)

    def test_first_interruption_has_no_previous_balance(self):
        self.interrupt()
        response = self.client.get(self.balance_url)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('last_confirmed', response.json())
        self.assertNotIn('data', response.json())

    def test_previous_balance_survives_navigation_and_retry_but_never_counts_as_current(self):
        confirmed = self.client.get(self.balance_url).json()
        self.assertEqual(confirmed['data']['balance'], 8000)
        self.interrupt()
        Movement.objects.create(account=self.account, kind='cargo', amount=1500,
                                description='Cargo posterior', occurred_at=timezone.now())
        self.assertEqual(self.client.get(reverse('saldo')).status_code, 200)
        previous = {'balance': 8000, 'updated_at': confirmed['updated_at']}
        for status in (503, 429):
            response = self.client.get(self.balance_url)
            self.assertEqual(response.status_code, status)
            self.assertEqual(response.json()['last_confirmed'], previous)
            self.assertNotIn('data', response.json())

        ServiceState.objects.filter(code='balance').update(available=True)
        future = timezone.now() + timedelta(seconds=settings.QUERY_RETRY_SECONDS + 1)
        with patch('django.utils.timezone.now', return_value=future):
            response = self.client.get(self.balance_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data']['balance'], 6500)
        self.assertNotIn('last_confirmed', response.json())

    def test_previous_balance_isolated_to_authorized_account_and_original_session(self):
        self.assertEqual(self.client.get(self.balance_url).status_code, 200)
        self.interrupt()

        separate_client = Client()
        separate_client.force_login(self.user)
        pending = separate_client.get(self.balance_url)
        self.assertEqual(pending.status_code, 503)
        self.assertNotIn('last_confirmed', pending.json())

        denied = self.client.get(reverse('api_saldo', args=[self.other_account.pk]))
        self.assertEqual(denied.status_code, 403)
        self.assertNotIn('last_confirmed', denied.json())

        self.client.post(reverse('salir'))
        expired = self.client.get(self.balance_url)
        self.assertEqual(expired.status_code, 401)
        self.assertNotIn('last_confirmed', expired.json())
