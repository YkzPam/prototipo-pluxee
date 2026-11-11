"""Comprobaciones de pagos ficticios, comercios y perfil.

Se usan exclusivamente cuentas, comercios y movimientos de la base temporal.
Ninguna prueba envía dinero ni consulta servicios externos.
"""
from datetime import timedelta
from unittest.mock import patch
import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from beneficios.models import (
    AuditEvent, BenefitAccount, DemoCard, Merchant, MerchantFavorite,
    Movement, Payment, PaymentThrottle, ServiceState,
)


class ExtendedPrototypeFlowsTests(TestCase):
    password = 'PruebaExtendida!2026'
    pin = '4826'

    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        hashed = make_password(cls.password)
        cls.alice = users.objects.create(username='alicia.demo', first_name='Alicia', last_name='Prueba', password=hashed)
        cls.bob = users.objects.create(username='bruno.demo', first_name='Bruno', last_name='Prueba', password=hashed)
        cls.admin = users.objects.create(username='admin.demo', first_name='Admin', password=hashed, is_staff=True)
        cls.account_a = BenefitAccount.objects.create(user=cls.alice, number_suffix='2001')
        cls.account_b = BenefitAccount.objects.create(user=cls.bob, number_suffix='2002')
        cls.card_a = DemoCard.objects.create(account=cls.account_a, status='active', pin_hash=make_password(cls.pin))
        cls.card_b = DemoCard.objects.create(account=cls.account_b, status='active', pin_hash=make_password('1593'))
        cls.merchant = Merchant.objects.create(code='DEMO-T01', name='Cafetería de prueba', category='Cafetería',
            commune='Santiago', address='Dirección sintética 100', description='Comercio exclusivamente ficticio', active=True)
        cls.other_merchant = Merchant.objects.create(code='DEMO-T02', name='Almacén de prueba', category='Almacén',
            commune='La Florida', address='Dirección sintética 200', description='Segundo comercio ficticio', active=True)
        cls.inactive_merchant = Merchant.objects.create(code='DEMO-T03', name='Local inhabilitado', category='Almacén',
            commune='Santiago', address='Dirección sintética 300', description='Comercio ficticio inhabilitado', active=False)
        Movement.objects.create(account=cls.account_a, kind='abono', amount=10000,
            description='Abono de prueba de pagos', occurred_at=timezone.now())
        Movement.objects.create(account=cls.account_b, kind='abono', amount=777,
            description='Abono de otra cuenta', occurred_at=timezone.now())
        ServiceState.objects.create(code='balance', label='Saldo', available=True)
        ServiceState.objects.create(code='movements', label='Movimientos', available=True)

    def sign_in(self, user=None):
        self.client.force_login(user or self.alice)
        session = self.client.session
        now = timezone.now().timestamp()
        session['auth_started_at'] = now
        session['last_activity_at'] = now
        session.save()

    def payment_data(self, **overrides):
        return {'merchant': self.merchant.pk, 'amount': '1200', 'pin': self.pin,
                'idempotency_key': str(uuid.uuid4()), **overrides}

    def payment_url(self):
        return reverse('pagar')

    def ledger_snapshot(self):
        return list(Movement.objects.order_by('pk').values())

    def test_valid_payment_creates_one_own_debit_receipt_and_persisted_balance(self):
        self.sign_in()
        response = self.client.post(self.payment_url(), self.payment_data())
        self.assertEqual(response.status_code, 302)
        payment = Payment.objects.get()
        self.assertEqual(payment.user_id, self.alice.pk)
        self.assertEqual(payment.account_id, self.account_a.pk)
        self.assertEqual(payment.merchant_id, self.merchant.pk)
        self.assertEqual(payment.amount, 1200)
        self.assertEqual(payment.balance_after, 8800)
        self.assertEqual(payment.movement.amount, 1200)
        self.assertEqual(payment.movement.kind, 'cargo')
        self.assertEqual(payment.movement.account_id, self.account_a.pk)
        self.assertRedirects(response, reverse('comprobante', args=[payment.pk]), fetch_redirect_response=False)
        self.assertEqual(self.client.get(response['Location']).status_code, 200)
        balance = self.client.get(reverse('api_saldo', args=[self.account_a.pk])).json()['data']['balance']
        self.assertEqual(balance, 8800)

    def test_same_payment_request_is_idempotent_and_does_not_debit_twice(self):
        self.sign_in()
        data = self.payment_data()
        first = self.client.post(self.payment_url(), data)
        snapshot = self.ledger_snapshot()
        duplicate = self.client.post(self.payment_url(), data)
        self.assertEqual(first.status_code, 302)
        self.assertEqual(duplicate.status_code, 302)
        self.assertEqual(duplicate['Location'], first['Location'])
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(Movement.objects.filter(kind='cargo', account=self.account_a).count(), 1)
        self.assertEqual(self.ledger_snapshot(), snapshot)

    def test_reusing_idempotency_key_with_other_amount_or_merchant_is_rejected(self):
        self.sign_in()
        data = self.payment_data()
        self.client.post(self.payment_url(), data)
        original = self.ledger_snapshot()
        for changes in ({'amount': '1300'}, {'merchant': self.other_merchant.pk}):
            with self.subTest(changes=changes):
                response = self.client.post(self.payment_url(), {**data, **changes})
                self.assertNotEqual(response.status_code, 302)
                self.assertEqual(Payment.objects.count(), 1)
                self.assertEqual(self.ledger_snapshot(), original)

    def test_payment_from_another_account_and_missing_receipt_are_not_disclosed(self):
        self.sign_in()
        self.client.post(self.payment_url(), self.payment_data())
        payment = Payment.objects.get()
        self.sign_in(self.bob)
        response = self.client.get(reverse('comprobante', args=[payment.pk]))
        self.assertIn(response.status_code, (403, 404))
        self.assertNotContains(response, str(payment.id), status_code=response.status_code)
        self.assertIn(self.client.get(reverse('comprobante', args=[uuid.uuid4()])).status_code, (403, 404))

    def test_payment_cannot_select_another_account_or_user_through_post_fields(self):
        self.sign_in()
        self.client.post(self.payment_url(), self.payment_data(account=self.account_b.pk, user=self.bob.pk))
        payment = Payment.objects.get()
        self.assertEqual(payment.user_id, self.alice.pk)
        self.assertEqual(payment.account_id, self.account_a.pk)
        self.assertFalse(Movement.objects.filter(account=self.account_b, kind='cargo').exists())

    def test_same_key_for_distinct_users_never_retrieves_foreign_receipt(self):
        self.sign_in()
        key = str(uuid.uuid4())
        self.client.post(self.payment_url(), self.payment_data(idempotency_key=key))
        first_payment = Payment.objects.get()
        self.sign_in(self.bob)
        response = self.client.post(self.payment_url(), self.payment_data(idempotency_key=key, amount='100', pin='1593'))
        self.assertEqual(response.status_code, 302)
        second_payment = Payment.objects.get(user=self.bob)
        self.assertNotEqual(second_payment.pk, first_payment.pk)
        self.assertNotEqual(response['Location'], reverse('comprobante', args=[first_payment.pk]))
        self.assertEqual(second_payment.balance_after, 677)

    def test_invalid_amounts_and_non_uuid_keys_cannot_create_payments(self):
        self.sign_in()
        original = self.ledger_snapshot()
        for amount in ('0', '-100', '1.5', 'texto', '1000001', '999999999999999999999'):
            with self.subTest(amount=amount):
                response = self.client.post(self.payment_url(), self.payment_data(amount=amount))
                self.assertNotEqual(response.status_code, 302)
                self.assertFalse(Payment.objects.exists())
                self.assertEqual(self.ledger_snapshot(), original)
        response = self.client.post(self.payment_url(), self.payment_data(idempotency_key='invalid'))
        self.assertNotEqual(response.status_code, 302)
        self.assertFalse(Payment.objects.exists())

    def test_insufficient_balance_rejects_payment_without_negative_ledger(self):
        self.sign_in()
        original = self.ledger_snapshot()
        response = self.client.post(self.payment_url(), self.payment_data(amount='10001'))
        self.assertNotEqual(response.status_code, 302)
        self.assertFalse(Payment.objects.exists())
        self.assertEqual(self.ledger_snapshot(), original)

    def test_inactive_or_nonexistent_merchant_is_rejected(self):
        self.sign_in()
        original = self.ledger_snapshot()
        for merchant in (self.inactive_merchant.pk, 999999):
            with self.subTest(merchant=merchant):
                response = self.client.post(self.payment_url(), self.payment_data(merchant=merchant))
                self.assertNotEqual(response.status_code, 302)
                self.assertFalse(Payment.objects.exists())
                self.assertEqual(self.ledger_snapshot(), original)

    def test_incorrect_pin_does_not_debit_and_is_never_written_to_audit(self):
        self.sign_in()
        wrong_pin = '8642'
        original = self.ledger_snapshot()
        response = self.client.post(self.payment_url(), self.payment_data(pin=wrong_pin))
        self.assertNotEqual(response.status_code, 302)
        self.assertFalse(Payment.objects.exists())
        self.assertEqual(self.ledger_snapshot(), original)
        audit_text = ' '.join(AuditEvent.objects.values_list('detail', flat=True))
        self.assertNotIn(wrong_pin, audit_text)
        self.assertNotIn(self.pin, audit_text)
        self.assertNotEqual(self.card_a.pin_hash, self.pin)
        self.assertTrue(check_password(self.pin, self.card_a.pin_hash))

    def test_pin_lockout_rejects_correct_pin_until_cooldown(self):
        self.sign_in()
        for _ in range(5):
            self.client.post(self.payment_url(), self.payment_data(pin='0000'))
        throttle = PaymentThrottle.objects.get(user=self.alice)
        self.assertGreater(throttle.blocked_until, timezone.now())
        blocked = self.client.post(self.payment_url(), self.payment_data())
        self.assertNotEqual(blocked.status_code, 302)
        self.assertFalse(Payment.objects.exists())
        with patch('django.utils.timezone.now', return_value=timezone.now() + timedelta(minutes=16)):
            # Tras esa espera también corresponde iniciar una sesión vigente;
            # el bloqueo del PIN persiste en BD y no depende de esa sesión.
            self.sign_in()
            accepted = self.client.post(self.payment_url(), self.payment_data())
        self.assertEqual(accepted.status_code, 302)
        self.assertEqual(Payment.objects.count(), 1)

    def test_blocked_card_cannot_pay_and_owner_can_unblock_only_own_card(self):
        self.sign_in()
        self.client.post(reverse('tarjeta'), {'action': 'block', 'account': self.account_b.pk})
        self.card_a.refresh_from_db()
        self.card_b.refresh_from_db()
        self.assertEqual(self.card_a.status, 'blocked')
        self.assertEqual(self.card_b.status, 'active')
        original = self.ledger_snapshot()
        denied = self.client.post(self.payment_url(), self.payment_data())
        self.assertNotEqual(denied.status_code, 302)
        self.assertEqual(self.ledger_snapshot(), original)
        self.assertFalse(Payment.objects.exists())
        self.client.post(reverse('tarjeta'), {'action': 'unblock'})
        self.card_a.refresh_from_db()
        self.assertEqual(self.card_a.status, 'active')
        self.assertEqual(self.client.post(self.payment_url(), self.payment_data()).status_code, 302)

    def test_service_interruptions_do_not_debit_or_create_receipts(self):
        self.sign_in()
        original = self.ledger_snapshot()
        for service_code in ('balance', 'movements'):
            with self.subTest(service=service_code):
                ServiceState.objects.filter(code=service_code).update(available=False)
                response = self.client.post(self.payment_url(), self.payment_data())
                self.assertNotEqual(response.status_code, 302)
                self.assertFalse(Payment.objects.exists())
                self.assertEqual(self.ledger_snapshot(), original)
                ServiceState.objects.filter(code=service_code).update(available=True)

    def test_database_audit_failure_rolls_back_payment_and_receipt_together(self):
        self.sign_in()
        original = self.ledger_snapshot()
        create_event = AuditEvent.objects.create

        def force_database_constraint_failure(**values):
            # Inyecta una infracción real NOT NULL en la bitácora. La capa de
            # pago debe revertir su cargo aunque el observador aísle el error.
            values['request_id'] = None
            return create_event(**values)

        with patch('beneficios.events.AuditEvent.objects.create', side_effect=force_database_constraint_failure):
            with self.assertLogs('beneficios.events', level='ERROR'):
                response = self.client.post(self.payment_url(), self.payment_data())
        self.assertEqual(response.status_code, 503)
        self.assertFalse(Payment.objects.exists())
        self.assertEqual(self.ledger_snapshot(), original)

    def test_favorite_toggle_is_scoped_to_authenticated_user(self):
        self.sign_in()
        self.client.post(reverse('favorito', args=[self.merchant.pk]), {'user': self.bob.pk})
        self.assertTrue(MerchantFavorite.objects.filter(user=self.alice, merchant=self.merchant).exists())
        self.assertFalse(MerchantFavorite.objects.filter(user=self.bob).exists())
        self.sign_in(self.bob)
        self.client.post(reverse('favorito', args=[self.merchant.pk]))
        self.assertEqual(MerchantFavorite.objects.filter(merchant=self.merchant).count(), 2)
        self.sign_in()
        self.client.post(reverse('favorito', args=[self.merchant.pk]))
        self.assertFalse(MerchantFavorite.objects.filter(user=self.alice, merchant=self.merchant).exists())
        self.assertTrue(MerchantFavorite.objects.filter(user=self.bob, merchant=self.merchant).exists())

    def test_merchant_search_filters_and_favorites_return_only_matching_active_records(self):
        self.sign_in()
        by_name = self.client.get(reverse('comercios'), {'q': 'Cafetería'})
        self.assertEqual(by_name.status_code, 200)
        self.assertEqual([item.pk for item in by_name.context['merchants']], [self.merchant.pk])
        filtered = self.client.get(reverse('comercios'), {'categoria': 'Almacén', 'comuna': 'La Florida'})
        self.assertEqual([item.pk for item in filtered.context['merchants']], [self.other_merchant.pk])
        MerchantFavorite.objects.create(user=self.alice, merchant=self.merchant)
        MerchantFavorite.objects.create(user=self.bob, merchant=self.other_merchant)
        favorites = self.client.get(reverse('comercios'), {'favoritos': '1'})
        self.assertEqual([item.pk for item in favorites.context['merchants']], [self.merchant.pk])
        all_items = self.client.get(reverse('comercios')).context['merchants']
        self.assertNotIn(self.inactive_merchant.pk, [item.pk for item in all_items])

    def test_removing_favorite_keeps_the_catalog_filters(self):
        self.sign_in()
        MerchantFavorite.objects.create(user=self.alice, merchant=self.merchant)
        filters = {'q': 'Cafetería', 'categoria': 'Cafetería', 'comuna': 'Santiago', 'favoritos': '1'}
        listing = reverse('comercios', query=filters)
        favorite = reverse('favorito', args=[self.merchant.pk], query=filters)
        page = self.client.get(listing)
        self.assertContains(page, f'action="{escape(favorite)}"')

        response = self.client.post(f'{favorite}&next=https://example.com/', follow=True)
        self.assertEqual(response.redirect_chain, [(listing, 302)])
        self.assertTrue(response.context['favorites_only'])
        self.assertFalse(response.context['merchants'])
        self.assertFalse(MerchantFavorite.objects.filter(user=self.alice, merchant=self.merchant).exists())

    def test_merchant_search_rejects_invalid_parameters_and_inactive_favorites(self):
        self.sign_in()
        for query in ({'q': '<script>'}, {'q': 'a' * 61}, {'categoria': 'inexistente'}, {'comuna': 'inexistente'}):
            with self.subTest(query=query):
                response = self.client.get(reverse('comercios'), query)
                self.assertEqual(response.status_code, 400)
                self.assertFalse(response.context['merchants'])
        self.assertEqual(self.client.post(reverse('favorito', args=[self.inactive_merchant.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('favorito', args=[self.merchant.pk])).status_code, 405)
        self.assertFalse(MerchantFavorite.objects.exists())

    def test_profile_changes_only_authenticated_users_validated_names(self):
        self.sign_in()
        response = self.client.post(reverse('perfil'), {'first_name': 'María José', 'last_name': 'Ryan-Pérez', 'user': self.bob.pk})
        self.assertEqual(response.status_code, 302)
        self.alice.refresh_from_db()
        self.bob.refresh_from_db()
        self.assertEqual(self.alice.first_name, 'María José')
        self.assertEqual(self.alice.last_name, 'Ryan-Pérez')
        self.assertEqual(self.bob.first_name, 'Bruno')
        # La pauta OWASP del curso también rechaza el apóstrofo.
        for first_name in ('<script>alert(1)</script>', 'A' * 41, 'Nombre123', '', "O'Ryan"):
            with self.subTest(first_name=first_name):
                invalid = self.client.post(reverse('perfil'), {'first_name': first_name, 'last_name': 'Prueba'})
                self.assertNotEqual(invalid.status_code, 302)
                self.alice.refresh_from_db()
                self.assertEqual(self.alice.first_name, 'María José')

    def test_new_functions_require_authentication_and_admin_cannot_use_beneficiary_payments(self):
        for url in (reverse('pagar'), reverse('comercios'), reverse('perfil'), reverse('tarjeta')):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 302)
        self.sign_in(self.admin)
        self.client.post(self.payment_url(), self.payment_data())
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(Movement.objects.filter(kind='cargo').exists())

    def test_new_mutating_flows_require_csrf_protection(self):
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.alice)
        posts = [
            (self.payment_url(), self.payment_data()),
            (reverse('tarjeta'), {'action': 'block'}),
            (reverse('perfil'), {'first_name': 'Otro', 'last_name': 'Nombre'}),
            (reverse('favorito', args=[self.merchant.pk]), {}),
        ]
        for url, data in posts:
            with self.subTest(url=url):
                self.assertEqual(protected.post(url, data).status_code, 403)
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(MerchantFavorite.objects.exists())
        self.card_a.refresh_from_db()
        self.alice.refresh_from_db()
        self.assertEqual(self.card_a.status, 'active')
        self.assertEqual(self.alice.first_name, 'Alicia')
