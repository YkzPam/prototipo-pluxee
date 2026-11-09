"""Pruebas de comportamiento: acceso, consulta, recuperación y segregación de cuentas.

La base de datos de prueba es independiente y todos los registros son sintéticos.
No se emplean credenciales ni servicios reales de Pluxee.
"""
from datetime import datetime, timedelta, timezone as datetime_timezone
from unittest.mock import patch
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from beneficios.events import DomainEvent, EventSubject
from beneficios.models import AuditEvent, BenefitAccount, LoginThrottle, Movement, ServiceState


class PrototypeWorkflowsTests(TestCase):
    password = 'ClaveDePrueba!2026'

    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        encoded = make_password(cls.password)
        cls.alice = user_model.objects.create(username='beneficiario.a', first_name='Andrea', password=encoded)
        cls.bob = user_model.objects.create(username='beneficiario.b', first_name='Bruno', password=encoded)
        cls.admin = user_model.objects.create(username='administrador', first_name='Admin', password=encoded, is_staff=True)
        cls.inactive = user_model.objects.create(username='inhabilitado', password=encoded, is_active=False)
        cls.account_a = BenefitAccount.objects.create(user=cls.alice, number_suffix='1001')
        cls.account_b = BenefitAccount.objects.create(user=cls.bob, number_suffix='1002')
        cls.credit = Movement.objects.create(account=cls.account_a, kind='abono', amount=10000,
            description='Abono de prueba', occurred_at=datetime(2026, 11, 1, 15, tzinfo=datetime_timezone.utc))
        cls.debit = Movement.objects.create(account=cls.account_a, kind='cargo', amount=2500,
            description='Compra de prueba', occurred_at=datetime(2026, 11, 3, 15, tzinfo=datetime_timezone.utc))
        Movement.objects.create(account=cls.account_b, kind='abono', amount=777,
            description='Registro exclusivo de otra cuenta', occurred_at=timezone.now())
        ServiceState.objects.create(code='balance', label='Saldo')
        ServiceState.objects.create(code='movements', label='Movimientos')

    def authenticate_client(self, user=None):
        self.client.force_login(user or self.alice)
        session = self.client.session
        now = timezone.now().timestamp()
        session['auth_started_at'] = now
        session['last_activity_at'] = now
        session.save()

    def balance_url(self, account=None):
        return reverse('api_saldo', args=[(account or self.account_a).pk])

    def movements_url(self, account=None):
        return reverse('api_movimientos', args=[(account or self.account_a).pk])

    def test_valid_login_establishes_server_session_and_audit(self):
        response = self.client.post(reverse('ingresar'), {'username': self.alice.username, 'password': self.password})
        self.assertRedirects(response, reverse('inicio'), fetch_redirect_response=False)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.alice.pk)
        self.assertIn('auth_started_at', self.client.session)
        self.assertTrue(AuditEvent.objects.filter(actor=self.alice, event_type='login', outcome='success').exists())
        cookie = response.cookies[settings.SESSION_COOKIE_NAME]
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['samesite'], 'Lax')

    def test_wrong_and_unknown_accounts_receive_same_generic_error(self):
        wrong = self.client.post(reverse('ingresar'), {'username': self.alice.username, 'password': 'Incorrecta!123'})
        unknown = self.client.post(reverse('ingresar'), {'username': 'cuenta.inexistente', 'password': 'Incorrecta!123'})
        self.assertEqual(wrong.context['form'].non_field_errors(), unknown.context['form'].non_field_errors())
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertEqual(AuditEvent.objects.filter(event_type='login', outcome='denied').count(), 2)

    def test_disabled_account_cannot_login(self):
        response = self.client.post(reverse('ingresar'), {'username': self.inactive.username, 'password': self.password})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].non_field_errors())
        self.assertNotIn('_auth_user_id', self.client.session)

    @override_settings(LOGIN_MAX_ATTEMPTS=2)
    def test_lockout_rejects_even_correct_password_until_timeout(self):
        data = {'username': self.alice.username, 'password': 'Incorrecta!123'}
        self.client.post(reverse('ingresar'), data)
        self.client.post(reverse('ingresar'), data)
        response = self.client.post(reverse('ingresar'), {**data, 'password': self.password})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertTrue(LoginThrottle.objects.filter(blocked_until__gt=timezone.now()).exists())
        future = timezone.now() + timedelta(seconds=settings.LOGIN_LOCK_SECONDS + 1)
        with patch('django.utils.timezone.now', return_value=future):
            response = self.client.post(reverse('ingresar'), {**data, 'password': self.password})
        self.assertEqual(response.status_code, 302)
        self.assertIn('_auth_user_id', self.client.session)

    def test_input_validation_rejects_missing_oversized_and_injection_inputs(self):
        cases = [
            {'username': '', 'password': self.password},
            {'username': 'a' * 151, 'password': self.password},
            {'username': "' OR 1=1 --", 'password': self.password},
            {'username': self.alice.username, 'password': 'x' * 129},
        ]
        for data in cases:
            with self.subTest(data={key: len(value) for key, value in data.items()}):
                response = self.client.post(reverse('ingresar'), data)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context['form'].errors)
                self.assertNotIn('_auth_user_id', self.client.session)

    def test_external_next_url_cannot_redirect_credentials_off_site(self):
        response = self.client.post(reverse('ingresar'), {'username': self.alice.username, 'password': self.password,
            'next': 'https://example.invalid/recibir'})
        self.assertRedirects(response, reverse('inicio'), fetch_redirect_response=False)

    def test_internal_next_url_is_preserved(self):
        response = self.client.post(reverse('ingresar'), {'username': self.alice.username, 'password': self.password,
            'next': reverse('movimientos')})
        self.assertRedirects(response, reverse('movimientos'), fetch_redirect_response=False)

    def test_guest_cannot_read_json_or_protected_page(self):
        for url in (self.balance_url(), self.movements_url()):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json()['status'], 'expired')
                self.assertNotIn('data', response.json())
        self.assertRedirects(self.client.get(reverse('inicio')), '/ingresar/?next=/', fetch_redirect_response=False)

    def test_account_owner_reads_balance_computed_from_persisted_movements(self):
        self.authenticate_client()
        response = self.client.get(self.balance_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'updated')
        self.assertEqual(response.json()['data'], {'balance': 7500, 'credited': 10000, 'spent': 2500, 'currency': 'CLP'})
        Movement.objects.create(account=self.account_a, kind='cargo', amount=500, description='Nueva compra', occurred_at=timezone.now())
        self.assertEqual(self.client.get(self.balance_url()).json()['data']['balance'], 7000)

    def test_reading_movements_returns_only_own_data_in_descending_date_order(self):
        self.authenticate_client()
        response = self.client.get(self.movements_url())
        self.assertEqual(response.status_code, 200)
        data = response.json()['data']
        self.assertEqual(data['total'], 2)
        self.assertEqual([row['id'] for row in data['items']], [self.debit.pk, self.credit.pk])
        self.assertNotContains(response, 'Registro exclusivo de otra cuenta')

    def test_account_id_changes_do_not_change_authorization(self):
        self.authenticate_client()
        for url in (self.balance_url(self.account_b), self.movements_url(self.account_b), reverse('api_saldo', args=[999999])):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 403)
                self.assertNotIn('data', response.json())
        self.assertEqual(AuditEvent.objects.filter(event_type='access', outcome='denied').count(), 3)

    def test_beneficiary_cannot_read_or_change_admin_services(self):
        self.authenticate_client()
        self.assertEqual(self.client.get(reverse('seguimiento')).status_code, 403)
        response = self.client.post(reverse('servicios'), {'service': 'balance', 'state': 'unavailable'})
        self.assertEqual(response.status_code, 403)
        self.assertTrue(ServiceState.objects.get(code='balance').available)

    def test_administrator_can_read_actual_events_but_not_other_accounts_balance(self):
        self.authenticate_client(self.admin)
        response = self.client.get(reverse('seguimiento'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['stats']['total'], AuditEvent.objects.count())
        self.assertEqual(response.context['event_types'], [])
        self.assertEqual(response.context['outcomes'], [])
        self.assertEqual(self.client.get(self.balance_url()).status_code, 403)
        self.assertRedirects(self.client.get(reverse('inicio')), reverse('seguimiento'), fetch_redirect_response=False)
        filtered = self.client.get(reverse('seguimiento'), {'event_type': 'password', 'outcome': 'success'})
        self.assertContains(filtered, '<option value="access">Control de acceso</option>', html=True)
        self.assertContains(filtered, '<option value="password" selected>Cambio de contraseña</option>', html=True)
        self.assertContains(filtered, '<option value="success" selected>Correcto</option>', html=True)
        self.assertNotContains(filtered, '<option value="login">Inicio de sesión</option>', html=True)

    def test_administrator_can_switch_only_valid_service_states_without_modifying_ledger(self):
        self.authenticate_client(self.admin)
        original = list(Movement.objects.values())
        response = self.client.post(reverse('servicios'), {'service': 'balance', 'state': 'unavailable', 'amount': 0})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ServiceState.objects.get(code='balance').available)
        self.assertEqual(list(Movement.objects.values()), original)
        self.client.post(reverse('servicios'), {'service': 'balance', 'state': 'invalid'})
        self.assertFalse(ServiceState.objects.get(code='balance').available)
        self.client.post(reverse('servicios'), {'service': 'balance', 'state': 'available'})
        self.assertTrue(ServiceState.objects.get(code='balance').available)
        self.assertEqual(self.client.get(reverse('servicios')).status_code, 405)

    @override_settings(QUERY_RETRY_SECONDS=4)
    def test_interrupted_balance_is_pending_without_zero_and_recovers_after_retry(self):
        self.authenticate_client()
        original = list(Movement.objects.values())
        ServiceState.objects.filter(code='balance').update(available=False)
        started_at = timezone.now()
        with patch('django.utils.timezone.now', return_value=started_at):
            response = self.client.get(self.balance_url())
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['status'], 'pending')
        self.assertEqual(response.headers.get('Retry-After'), '4')
        self.assertNotIn('data', response.json())
        self.assertIn('_auth_user_id', self.client.session)
        self.assertEqual(list(Movement.objects.values()), original)
        ServiceState.objects.filter(code='balance').update(available=True)
        for elapsed, remaining in ((2.25, '2'), (3.75, '1')):
            with self.subTest(elapsed=elapsed), patch(
                'django.utils.timezone.now', return_value=started_at + timedelta(seconds=elapsed),
            ):
                limited = self.client.get(self.balance_url())
                self.assertEqual(limited.status_code, 429)
                self.assertEqual(limited.headers.get('Retry-After'), remaining)
        with patch('django.utils.timezone.now', return_value=started_at + timedelta(seconds=4)):
            recovered = self.client.get(self.balance_url())
        self.assertEqual(recovered.status_code, 200)
        self.assertNotIn('Retry-After', recovered)
        self.assertEqual(recovered.json()['data']['balance'], 7500)
        self.assertEqual(list(Movement.objects.values()), original)
        self.assertEqual(AuditEvent.objects.filter(event_type='balance', outcome='pending').count(), 1)

    def test_movements_interruption_and_empty_history_are_distinct(self):
        self.authenticate_client()
        ServiceState.objects.filter(code='movements').update(available=False)
        pending = self.client.get(self.movements_url())
        self.assertEqual(pending.status_code, 503)
        self.assertEqual(pending.headers.get('Retry-After'), str(settings.QUERY_RETRY_SECONDS))
        self.assertNotIn('data', pending.json())
        balance = self.client.get(self.balance_url())
        self.assertEqual(balance.status_code, 200)
        self.assertNotIn('Retry-After', balance)
        ServiceState.objects.filter(code='movements').update(available=True)
        future = timezone.now() + timedelta(seconds=settings.QUERY_RETRY_SECONDS + 1)
        with patch('django.utils.timezone.now', return_value=future):
            empty = self.client.get(self.movements_url(), {'desde': '2025-01-01', 'hasta': '2025-01-02'})
        self.assertEqual(empty.status_code, 200)
        self.assertNotIn('Retry-After', empty)
        self.assertEqual(empty.json()['data']['items'], [])
        self.assertEqual(empty.json()['status'], 'updated')

    def test_filters_constrain_date_kind_and_pagination(self):
        self.authenticate_client()
        response = self.client.get(self.movements_url(), {'desde': '2026-11-02', 'hasta': '2026-11-04', 'tipo': 'cargo'})
        self.assertEqual([item['id'] for item in response.json()['data']['items']], [self.debit.pk])
        past_end = self.client.get(self.movements_url(), {'tipo': 'cargo', 'page': 200})
        data = past_end.json()['data']
        self.assertEqual([item['id'] for item in data['items']], [self.debit.pk])
        self.assertEqual(data['page'], data['pages'])
        self.assertEqual(data['total'], 1)

    def test_movement_filter_offers_own_stored_kinds_and_keeps_a_valid_deep_link(self):
        self.authenticate_client(self.bob)
        movement_page = reverse('movimientos')
        response = self.client.get(movement_page)
        self.assertContains(response, '<option value="abono">Abono</option>', html=True)
        self.assertNotContains(response, '<option value="cargo">Compra</option>', html=True)
        deep_link = self.client.get(movement_page, {'tipo': 'cargo'})
        self.assertContains(deep_link, '<option value="cargo">Compra</option>', html=True)
        invalid = self.client.get(movement_page, {'tipo': 'desconocido'})
        self.assertNotContains(invalid, '<option value="desconocido">', html=False)

    def test_invalid_filters_are_rejected_without_query_result(self):
        self.authenticate_client()
        for filters in ({'desde': 'not-a-date'}, {'desde': '2026-11-04', 'hasta': '2026-11-01'},
                        {'tipo': 'DROP TABLE'}, {'page': 0}, {'page': 100001}):
            with self.subTest(filters=filters):
                response = self.client.get(self.movements_url(), filters)
                self.assertEqual(response.status_code, 400)
                self.assertNotIn('data', response.json())

    def test_navigation_refresh_keeps_session_without_extending_absolute_start(self):
        self.authenticate_client()
        created = self.client.session['auth_started_at']
        for url in (reverse('inicio'), reverse('saldo'), reverse('movimientos'), self.balance_url()):
            self.assertEqual(self.client.get(url).status_code, 200)
            self.assertEqual(self.client.session['auth_started_at'], created)
            self.assertEqual(int(self.client.session['_auth_user_id']), self.alice.pk)

    def test_active_heartbeat_updates_activity_without_resetting_absolute_limit(self):
        self.authenticate_client()
        session = self.client.session
        created = timezone.now().timestamp() - 300
        session['auth_started_at'] = created
        session['last_activity_at'] = timezone.now().timestamp() - 60
        session.save()
        previous_activity = self.client.session['last_activity_at']
        response = self.client.post(reverse('actividad'))
        self.assertEqual(response.status_code, 200)
        self.assertGreater(self.client.session['last_activity_at'], previous_activity)
        self.assertEqual(self.client.session['auth_started_at'], created)

    def test_idle_timeout_invalidates_old_session_and_logs_reason(self):
        self.authenticate_client()
        session = self.client.session
        session['last_activity_at'] = timezone.now().timestamp() - settings.SESSION_IDLE_SECONDS - 1
        session.save()
        old_cookie = self.client.cookies[settings.SESSION_COOKIE_NAME].value
        response = self.client.get(self.balance_url())
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['status'], 'expired')
        self.assertIn('inactividad', response.json()['message'])
        self.assertNotIn('_auth_user_id', self.client.session)
        replay = Client()
        replay.cookies[settings.SESSION_COOKIE_NAME] = old_cookie
        self.assertEqual(replay.get(self.balance_url()).status_code, 401)
        self.assertTrue(AuditEvent.objects.filter(event_type='expired', actor=self.alice).exists())

    def test_absolute_timeout_applies_even_with_recent_activity(self):
        self.authenticate_client()
        session = self.client.session
        session['auth_started_at'] = timezone.now().timestamp() - settings.SESSION_MAX_SECONDS - 1
        session['last_activity_at'] = timezone.now().timestamp()
        session.save()
        response = self.client.get(self.balance_url())
        self.assertEqual(response.status_code, 401)
        self.assertIn('duración máxima', response.json()['message'])
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_expired_html_redirects_with_reason_and_security_headers(self):
        self.authenticate_client()
        session = self.client.session
        session['last_activity_at'] = timezone.now().timestamp() - settings.SESSION_IDLE_SECONDS - 1
        session.save()
        response = self.client.get(reverse('inicio'), follow=True)
        self.assertEqual(response.redirect_chain[0][0], reverse('ingresar'))
        self.assertContains(response, 'inactividad')
        self.assertEqual(response['Cache-Control'], 'no-store, private')
        self.assertIn("frame-ancestors 'none'", response['Content-Security-Policy'])

    def test_logout_invalidates_cookie_and_cannot_be_triggered_with_get(self):
        self.authenticate_client()
        self.assertEqual(self.client.get(reverse('salir')).status_code, 405)
        old_cookie = self.client.cookies[settings.SESSION_COOKIE_NAME].value
        self.assertEqual(self.client.post(reverse('salir')).status_code, 302)
        replay = Client()
        replay.cookies[settings.SESSION_COOKIE_NAME] = old_cookie
        self.assertEqual(replay.get(self.balance_url()).status_code, 401)
        self.assertTrue(AuditEvent.objects.filter(actor=self.alice, event_type='logout').exists())

    def test_post_requires_csrf_token_even_for_authenticated_administrator(self):
        protected = Client(enforce_csrf_checks=True)
        self.assertEqual(protected.post(reverse('ingresar'), {'username': self.alice.username, 'password': self.password}).status_code, 403)
        protected.force_login(self.admin)
        self.assertEqual(protected.post(reverse('servicios'), {'service': 'balance', 'state': 'unavailable'}).status_code, 403)
        self.assertEqual(protected.post(reverse('salir')).status_code, 403)
        self.assertTrue(ServiceState.objects.get(code='balance').available)

    def test_valid_csrf_form_token_allows_authorized_request(self):
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.alice)
        page = protected.get(reverse('inicio'))
        self.assertEqual(page.status_code, 200)
        token = protected.cookies[settings.CSRF_COOKIE_NAME].value
        response = protected.post(reverse('actividad'), {'csrfmiddlewaretoken': token})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'updated')

    def test_password_is_hashed_and_strength_policy_rejects_weak_values(self):
        self.assertNotEqual(self.alice.password, self.password)
        self.assertTrue(self.alice.password.startswith('pbkdf2_sha256$'))
        self.assertTrue(check_password(self.password, self.alice.password))
        for password in ('corta1!', '1234567890123456', 'sololetraslargas', 'LetrasYNumeros2026'):
            with self.subTest(password_length=len(password)):
                with self.assertRaises(ValidationError):
                    validate_password(password, self.alice)

    def test_password_change_requires_current_secret_and_keeps_authorized_session(self):
        self.authenticate_client()
        new_password = 'OtraClaveFuerte!2027'
        bad = self.client.post(reverse('cambiar_clave'), {'old_password': 'equivocada', 'new_password1': new_password, 'new_password2': new_password})
        self.assertEqual(bad.status_code, 200)
        self.assertTrue(bad.context['form'].errors)
        good = self.client.post(reverse('cambiar_clave'), {'old_password': self.password, 'new_password1': new_password, 'new_password2': new_password})
        self.assertEqual(good.status_code, 302)
        self.alice.refresh_from_db()
        self.assertTrue(self.alice.check_password(new_password))
        self.assertEqual(self.client.get(self.balance_url()).status_code, 200)

    def test_audit_rows_have_trace_and_do_not_include_password_or_reusable_session(self):
        self.client.post(reverse('ingresar'), {'username': self.alice.username, 'password': self.password})
        cookie = self.client.cookies[settings.SESSION_COOKIE_NAME].value
        self.client.get(self.balance_url())
        self.client.post(reverse('salir'))
        rows = list(AuditEvent.objects.values())
        self.assertEqual(len(rows), 3)
        for row in rows:
            self.assertIsNotNone(row['created_at'])
            self.assertIsInstance(row['request_id'], uuid.UUID)
            self.assertNotIn(self.password, str(row))
            self.assertNotIn(cookie, str(row))

    def test_html_escapes_stored_account_text_and_pages_have_defensive_headers(self):
        self.authenticate_client()
        self.account_a.public_label = '<script>alert("prueba")</script>'
        self.account_a.save()
        response = self.client.get(reverse('saldo'))
        self.assertNotContains(response, '<script>alert("prueba")</script>')
        self.assertContains(response, '&lt;script&gt;')
        self.assertEqual(response['X-Frame-Options'], 'DENY')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response['Cache-Control'], 'no-store, private')

    def test_ledger_rejects_zero_amount_before_encryption(self):
        count_before = self.account_a.movements.count()
        with self.assertRaises(ValidationError), transaction.atomic():
            Movement.objects.create(account=self.account_a, kind='cargo', amount=0,
                description='Dato inválido', occurred_at=timezone.now())
        self.assertEqual(self.account_a.movements.count(), count_before)

    def test_failure_of_one_observer_does_not_block_other_observers(self):
        received = []

        class FailedObserver:
            def update(self, event):
                raise RuntimeError('Fallo controlado sin información sensible')

        class SuccessfulObserver:
            def update(self, event):
                received.append(event)

        event = DomainEvent(self.alice, 'balance', 'success', 'Consulta de prueba', uuid.uuid4())
        with self.assertLogs('beneficios.events', level='ERROR') as captured:
            success = EventSubject([FailedObserver(), SuccessfulObserver()]).notify(event)
        self.assertFalse(success)
        self.assertEqual(received, [event])
        self.assertNotIn(self.password, '\n'.join(captured.output))

    def test_audit_failure_is_explicit_without_falsifying_balance_result(self):
        self.authenticate_client()
        with patch('beneficios.events.AuditObserver.update', side_effect=RuntimeError('Fallo de bitácora controlado')):
            with self.assertLogs('beneficios.events', level='ERROR'):
                response = self.client.get(self.balance_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data']['balance'], 7500)
        self.assertFalse(response.json()['audit_recorded'])
        self.assertFalse(AuditEvent.objects.filter(event_type='balance').exists())
