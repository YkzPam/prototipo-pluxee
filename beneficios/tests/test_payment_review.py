from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from beneficios.models import BenefitAccount, DemoCard, Merchant, Movement, Payment, PaymentThrottle, ServiceState


class PaymentReviewTests(TestCase):
    pin = '7834'

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username='revision.pagos')
        cls.account = BenefitAccount.objects.create(user=cls.user, number_suffix='1093')
        cls.card = DemoCard.objects.create(account=cls.account, pin_hash=make_password(cls.pin))
        cls.merchant = Merchant.objects.create(code='REV001', name='Almacén Campus', category='Almacén',
                                               commune='Santiago', address='Catálogo local')
        Movement.objects.create(account=cls.account, kind=Movement.Kind.CREDIT, amount=10000,
                                description='Abono inicial', occurred_at=timezone.now())
        ServiceState.objects.create(code='balance', label='Saldo')
        ServiceState.objects.create(code='movements', label='Movimientos')

    def setUp(self):
        self.client.force_login(self.user)
        self.url = reverse('pagar')

    def review(self, **changes):
        values = {'payment_step': 'review', 'method': 'online', 'merchant': self.merchant.pk,
                  'amount': '1200', 'pin': self.pin, 'idempotency_key': str(uuid4()), **changes}
        response = self.client.post(self.url, values)
        self.assertEqual(response.status_code, 302)
        rendered = self.client.get(response.url)
        self.assertEqual(rendered.status_code, 200)
        return rendered.context['review']['token'], values, rendered

    def confirm(self, token, **changes):
        return self.client.post(self.url, {'payment_step': 'confirm', 'review_token': token, **changes})

    def test_ui_reviews_server_values_before_charge_and_ignores_changed_posted_fields(self):
        self.assertContains(self.client.get(self.url), 'name="payment_step" value="review"')
        token, values, rendered = self.review()
        self.assertContains(rendered, 'Resumen del pago')
        self.assertEqual(rendered.context['review']['balance'], 10000)
        self.assertEqual(rendered.context['review']['balance_after'], 8800)
        self.assertNotContains(rendered, 'value="7834"')
        self.assertNotIn('pin', self.client.session['payment_reviews'][token])
        self.assertNotIn('dynamic_code', self.client.session['payment_reviews'][token])
        self.assertIn('no-store', rendered.headers['Cache-Control'])
        self.assertFalse(Payment.objects.exists())

        confirmed = self.confirm(token, amount='999999', merchant='999999', method='card', pin='1111')
        payment = Payment.objects.get()
        self.assertEqual(payment.amount, 1200)
        self.assertEqual(payment.method, Payment.Method.ONLINE)
        self.assertEqual(str(payment.idempotency_key), values['idempotency_key'])
        self.assertRedirects(confirmed, reverse('comprobante', args=[payment.pk]), fetch_redirect_response=False)
        self.assertRedirects(self.confirm(token), confirmed.url, fetch_redirect_response=False)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(Movement.objects.filter(kind=Movement.Kind.DEBIT).count(), 1)

    def test_editing_and_expiration_require_a_new_review(self):
        token, _, _ = self.review()
        edit = self.client.post(self.url, {'payment_step': 'edit', 'review_token': token})
        self.assertEqual(edit.status_code, 200)
        self.assertEqual(edit.context['form']['amount'].value(), 1200)
        self.assertIsNone(edit.context['form']['pin'].value())
        self.assertEqual(self.confirm(token).status_code, 409)

        token, _, _ = self.review()
        session = self.client.session
        reviews = session['payment_reviews']
        reviews[token]['expires_at'] = (timezone.now() - timedelta(seconds=1)).timestamp()
        session['payment_reviews'] = reviews
        session.save()
        self.assertEqual(self.confirm(token).status_code, 409)
        self.assertFalse(Payment.objects.exists())

    def test_other_session_and_changed_card_cannot_use_the_authorization(self):
        token, _, _ = self.review()
        other_session = Client()
        other_session.force_login(self.user)
        stolen = other_session.post(self.url, {'payment_step': 'confirm', 'review_token': token})
        self.assertEqual(stolen.status_code, 409)
        DemoCard.objects.filter(pk=self.card.pk).update(pin_hash=make_password('6842'))
        self.assertEqual(self.confirm(token).status_code, 400)
        self.assertFalse(Payment.objects.exists())

    def test_final_confirmation_rechecks_balance_service_and_required_audit(self):
        token, _, _ = self.review()
        ServiceState.objects.filter(code='movements').update(available=False)
        unavailable = self.confirm(token)
        self.assertEqual(unavailable.status_code, 503)
        self.assertEqual(unavailable.context['review']['token'], token)
        self.assertFalse(Payment.objects.exists())
        ServiceState.objects.filter(code='movements').update(available=True)
        with patch('beneficios.views_extra.record', return_value=False):
            self.assertEqual(self.confirm(token).status_code, 503)
        self.assertFalse(Payment.objects.exists())

        Movement.objects.create(account=self.account, kind=Movement.Kind.CREDIT, amount=500,
                                description='Otro abono', occurred_at=timezone.now())
        changed = self.confirm(token)
        self.assertContains(changed, 'El saldo cambió desde la revisión.', status_code=409)
        self.assertFalse(Payment.objects.exists())
        fresh, _, _ = self.review()
        self.assertEqual(self.confirm(fresh).status_code, 302)
        self.assertEqual(Payment.objects.get().balance_after, 9300)

    def test_qr_and_dynamic_review_keep_their_credential_rules(self):
        token, _, _ = self.review(method='qr', qr_code='rev001')
        self.assertEqual(self.confirm(token).status_code, 302)
        with patch('beneficios.views_extra.secrets.randbelow', return_value=932):
            issued = self.client.post(reverse('generar_clave_dinamica'), {'clave-pin': self.pin})
        self.assertEqual(issued.status_code, 200)
        code = issued.context['issued_code']
        token, _, rendered = self.review(method='dynamic', dynamic_code=code, pin='')
        self.card.refresh_from_db()
        self.assertTrue(self.card.dynamic_code_digest)
        self.assertNotContains(rendered, f'value="{code}"')
        self.assertNotIn('dynamic_code', self.client.session['payment_reviews'][token])
        self.assertEqual(self.confirm(token).status_code, 302)
        self.card.refresh_from_db()
        self.assertEqual(self.card.dynamic_code_digest, '')
        self.assertEqual(Payment.objects.count(), 2)

    def test_wrong_preview_pin_uses_existing_throttle_and_confirmation_needs_csrf(self):
        denied = self.client.post(self.url, {'payment_step': 'review', 'method': 'online',
            'merchant': self.merchant.pk, 'amount': '1200', 'pin': '1111', 'idempotency_key': str(uuid4())})
        self.assertEqual(denied.status_code, 400)
        self.assertEqual(PaymentThrottle.objects.get(user=self.user).failures, 1)
        token, _, _ = self.review()
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.cookies = self.client.cookies
        self.assertEqual(csrf_client.post(self.url, {'payment_step': 'confirm', 'review_token': token}).status_code, 403)
        self.assertFalse(Payment.objects.exists())
