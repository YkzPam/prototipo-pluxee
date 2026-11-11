"""Comprobaciones de los medios de pago simulados con datos de prueba."""
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from beneficios.models import AuditEvent, BenefitAccount, DemoCard, Merchant, Movement, Payment, PaymentThrottle, ServiceState


class PaymentMethodTests(TestCase):
    pin = '4826'

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username='medios.pago')
        cls.account = BenefitAccount.objects.create(user=cls.user, number_suffix='7812')
        cls.card = DemoCard.objects.create(account=cls.account, pin_hash=make_password(cls.pin))
        cls.merchant = Merchant.objects.create(code='DEMO-QR01', name='Comercio de prueba',
                                               category='Cafetería', commune='Santiago',
                                               address='Dirección de prueba 100')
        cls.inactive_merchant = Merchant.objects.create(
            code='DEMO-QR03', name='Comercio inactivo', category='Cafetería', commune='Santiago',
            address='Dirección de prueba 300', active=False,
        )
        Movement.objects.create(account=cls.account, kind=Movement.Kind.CREDIT, amount=10000,
                                description='Abono de prueba', occurred_at=timezone.now())
        ServiceState.objects.create(code='balance', label='Saldo')
        ServiceState.objects.create(code='movements', label='Movimientos')

    def setUp(self):
        self.client.force_login(self.user)
        self.pay_url = reverse('pagar')
        self.issue_url = reverse('generar_clave_dinamica')

    def payment_data(self, **fields):
        return {'merchant': self.merchant.pk, 'amount': '1000', 'idempotency_key': str(uuid4()), **fields}

    def issue(self):
        with patch('beneficios.views_extra.secrets.randbelow', return_value=72):
            response = self.client.post(self.issue_url, {'clave-pin': self.pin})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['issued_code'], '0072')
        self.card.refresh_from_db()
        return response.context['issued_code']

    def test_qr_requires_the_selected_merchants_code_and_labels_the_receipt(self):
        rejected = self.client.post(self.pay_url, self.payment_data(method='qr', qr_code='DEMO-QR02', pin=self.pin))
        self.assertContains(rejected, 'El código QR no corresponde al comercio seleccionado.', status_code=400)
        self.assertFalse(Payment.objects.exists())

        accepted = self.client.post(self.pay_url, self.payment_data(method='qr', qr_code='demo-qr01', pin=self.pin))
        payment = Payment.objects.get()
        self.assertEqual(payment.method, Payment.Method.QR)
        self.assertRedirects(accepted, reverse('comprobante', args=[payment.pk]), fetch_redirect_response=False)
        self.assertContains(self.client.get(accepted['Location']), payment.get_method_display())
        self.assertEqual(payment.balance_after, 9000)

    def test_qr_code_alone_identifies_the_commerce(self):
        data = self.payment_data(method='qr', qr_code=' demo-qr01 ', pin=self.pin)
        del data['merchant']

        accepted = self.client.post(self.pay_url, data)

        self.assertEqual(accepted.status_code, 302)
        payment = Payment.objects.get()
        self.assertRedirects(accepted, reverse('comprobante', args=[payment.pk]), fetch_redirect_response=False)
        self.assertEqual(payment.merchant_id, self.merchant.pk)
        self.assertEqual(payment.method, Payment.Method.QR)

    def test_qr_rejects_unknown_or_inactive_codes(self):
        for code in ('DEMO-QR02', self.inactive_merchant.code):
            with self.subTest(code=code):
                data = self.payment_data(method='qr', qr_code=code, pin=self.pin)
                del data['merchant']

                rejected = self.client.post(self.pay_url, data)

                self.assertContains(
                    rejected, 'El código ingresado no identifica a un comercio activo.', status_code=400,
                )
        self.assertFalse(Payment.objects.exists())

    def test_qr_catalog_offers_active_codes_and_prefills_the_chosen_commerce(self):
        catalog = self.client.get(self.pay_url, {'metodo': 'qr'})
        self.assertContains(catalog, f'value="{self.merchant.code}"')
        self.assertNotContains(catalog, self.inactive_merchant.code)

        prefilled = self.client.get(self.pay_url, {'metodo': 'qr', 'comercio': self.merchant.pk})
        self.assertEqual(prefilled.context['form']['qr_code'].value(), self.merchant.code)

    def test_legacy_request_still_uses_online_and_card_has_its_own_receipt(self):
        missing_merchant = self.payment_data(pin=self.pin)
        del missing_merchant['merchant']
        rejected = self.client.post(self.pay_url, missing_merchant)
        self.assertEqual(rejected.status_code, 400)
        self.assertIn('merchant', rejected.context['form'].errors)

        for fields, expected in (({}, Payment.Method.ONLINE), ({'method': 'card'}, Payment.Method.CARD)):
            with self.subTest(method=expected):
                response = self.client.post(self.pay_url, self.payment_data(pin=self.pin, **fields))
                self.assertEqual(response.status_code, 302)
                payment = Payment.objects.get(method=expected)
                self.assertContains(self.client.get(response['Location']), payment.get_method_display())

    def test_dynamic_code_is_bound_to_the_issuing_session_and_has_a_90_minute_limit(self):
        before = timezone.now()
        code = self.issue()
        self.assertGreaterEqual(self.card.dynamic_expires_at, before + timedelta(minutes=90))
        self.assertLessEqual(self.card.dynamic_expires_at, timezone.now() + timedelta(minutes=90))
        self.assertRegex(self.card.dynamic_code_digest, r'^[0-9a-f]{64}$')
        audit = AuditEvent.objects.get(event_type=AuditEvent.Type.CARD)
        self.assertNotIn(code, audit.detail)

        other_session = Client()
        other_session.force_login(self.user)
        self.assertNotEqual(other_session.session.session_key, self.client.session.session_key)
        rejected = other_session.post(self.pay_url, self.payment_data(method='dynamic', dynamic_code=code))
        self.assertEqual(rejected.status_code, 400)
        self.assertFalse(Payment.objects.exists())

        DemoCard.objects.filter(pk=self.card.pk).update(dynamic_expires_at=timezone.now() - timedelta(seconds=1))
        expired = self.client.post(self.pay_url, self.payment_data(method='dynamic', dynamic_code=code))
        self.assertContains(expired, 'La clave dinámica no coincide, venció o ya se utilizó.', status_code=400)
        self.assertFalse(Payment.objects.exists())

    def test_dynamic_code_is_consumed_once_and_an_identical_retry_returns_the_receipt(self):
        code = self.issue()
        data = self.payment_data(method='dynamic', dynamic_code=code)
        first = self.client.post(self.pay_url, data)
        self.assertEqual(first.status_code, 302)
        payment = Payment.objects.get()
        self.assertEqual(payment.method, Payment.Method.DYNAMIC)
        self.assertContains(self.client.get(first['Location']), payment.get_method_display())
        self.card.refresh_from_db()
        self.assertEqual(self.card.dynamic_code_digest, '')
        self.assertIsNone(self.card.dynamic_expires_at)

        retry = self.client.post(self.pay_url, data)
        self.assertRedirects(retry, first['Location'], fetch_redirect_response=False)
        conflict = self.client.post(self.pay_url, {**data, 'method': 'card', 'pin': self.pin})
        self.assertEqual(conflict.status_code, 409)
        reused = self.client.post(self.pay_url, self.payment_data(method='dynamic', dynamic_code=code))
        self.assertEqual(reused.status_code, 400)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(Movement.objects.filter(account=self.account, kind=Movement.Kind.DEBIT).count(), 1)

    def test_audit_failure_rolls_back_the_charge_and_preserves_the_unspent_code(self):
        code = self.issue()
        digest, expires_at = self.card.dynamic_code_digest, self.card.dynamic_expires_at
        data = self.payment_data(method='dynamic', dynamic_code=code)
        with patch('beneficios.views_extra.record', return_value=False):
            unavailable = self.client.post(self.pay_url, data)
        self.assertEqual(unavailable.status_code, 503)
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(Movement.objects.filter(account=self.account, kind=Movement.Kind.DEBIT).exists())
        self.card.refresh_from_db()
        self.assertEqual(self.card.dynamic_code_digest, digest)
        self.assertEqual(self.card.dynamic_expires_at, expires_at)
        self.assertEqual(self.client.post(self.pay_url, data).status_code, 302)

    def test_invalid_pin_blocked_attempts_and_blocked_card_cannot_issue_a_code(self):
        wrong_pin = self.client.post(self.issue_url, {'clave-pin': '1111'})
        self.assertContains(wrong_pin, 'El PIN de demostración no es válido.', status_code=400)
        self.assertEqual(PaymentThrottle.objects.get(user=self.user).failures, 1)

        PaymentThrottle.objects.filter(user=self.user).update(blocked_until=timezone.now() + timedelta(minutes=15))
        throttled = self.client.post(self.issue_url, {'clave-pin': self.pin})
        self.assertContains(throttled, 'La validación está bloqueada temporalmente.', status_code=429)

        DemoCard.objects.filter(pk=self.card.pk).update(status=DemoCard.Status.BLOCKED)
        blocked_card = self.client.post(self.issue_url, {'clave-pin': self.pin})
        self.assertContains(blocked_card, 'La tarjeta está bloqueada.', status_code=409)
        self.card.refresh_from_db()
        self.assertEqual(self.card.dynamic_code_digest, '')
        self.assertIsNone(self.card.dynamic_expires_at)
