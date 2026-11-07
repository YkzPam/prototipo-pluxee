from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from beneficios.models import BenefitAccount


class TemporaryPasswordTests(TestCase):
    temporary_password = 'ClaveTemporal!2026'
    new_password = 'OtraClaveFuerte!2027'

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username='beneficiario.provisional', password=cls.temporary_password,
            must_change_password=True,
        )
        cls.account = BenefitAccount.objects.create(user=cls.user, number_suffix='1001')

    def change_data(self, new_password=None):
        new_password = new_password or self.new_password
        return {
            'old_password': self.temporary_password,
            'new_password1': new_password,
            'new_password2': new_password,
        }

    def test_login_requires_change_and_ignores_requested_destination(self):
        for staff in (False, True):
            with self.subTest(staff=staff):
                self.user.is_staff = staff
                self.user.save(update_fields=['is_staff'])
                client = Client()
                login = client.post(reverse('ingresar'), {
                    'username': self.user.username,
                    'password': self.temporary_password,
                    'next': reverse('seguimiento'),
                })
                change_url = reverse('cambiar_clave')
                self.assertRedirects(login, change_url, fetch_redirect_response=False)
                self.assertContains(client.get(change_url), 'se debe cambiar la contraseña temporal')
                for name in ('inicio', 'saldo', 'pagar', 'seguimiento'):
                    self.assertRedirects(client.get(reverse(name)), change_url, fetch_redirect_response=False)
                self.assertRedirects(client.post(reverse('salir')), reverse('ingresar'))

    def test_pending_change_blocks_api_and_heartbeat_without_renewing_session(self):
        self.client.force_login(self.user)
        self.client.get(reverse('cambiar_clave'))
        last_activity = self.client.session['last_activity_at']
        responses = (
            self.client.get(reverse('api_saldo', args=[self.account.pk])),
            self.client.post(reverse('actividad')),
        )
        for response in responses:
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()['status'], 'password_change_required')
            self.assertEqual(response.json()['change_password_url'], reverse('cambiar_clave'))
        self.assertEqual(self.client.session['last_activity_at'], last_activity)

    def test_invalid_or_missing_csrf_change_leaves_temporary_password_in_place(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        change_url = reverse('cambiar_clave')
        self.assertEqual(client.post(change_url, self.change_data()).status_code, 403)
        client.get(change_url)
        csrf = client.cookies[settings.CSRF_COOKIE_NAME].value
        for data in (
            {**self.change_data(), 'old_password': 'equivocada'},
            self.change_data(self.temporary_password),
            self.change_data('corta!1'),
        ):
            response = client.post(change_url, {**data, 'csrfmiddlewaretoken': csrf})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form'].errors)
        self.user.refresh_from_db()
        self.assertTrue(self.user.must_change_password)
        self.assertTrue(self.user.check_password(self.temporary_password))

    def test_successful_change_rotates_session_and_restores_only_allowed_access(self):
        self.client.force_login(self.user)
        another_session = Client()
        another_session.force_login(self.user)
        cookie_name = settings.SESSION_COOKIE_NAME
        prior_cookie = self.client.cookies[cookie_name].value

        response = self.client.post(reverse('cambiar_clave'), self.change_data())

        self.assertRedirects(response, reverse('inicio'), fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertFalse(self.user.must_change_password)
        self.assertFalse(self.user.check_password(self.temporary_password))
        self.assertTrue(self.user.check_password(self.new_password))
        self.assertNotEqual(self.client.cookies[cookie_name].value, prior_cookie)
        self.assertEqual(self.client.get(reverse('inicio')).status_code, 200)
        self.assertEqual(self.client.get(reverse('seguimiento')).status_code, 403)
        self.assertEqual(another_session.post(reverse('actividad')).status_code, 401)

        replay = Client()
        replay.cookies[cookie_name] = prior_cookie
        self.assertEqual(replay.post(reverse('actividad')).status_code, 401)

        destination = reverse('saldo')
        login = replay.post(reverse('ingresar'), {
            'username': self.user.username, 'password': self.new_password, 'next': destination,
        })
        self.assertRedirects(login, destination, fetch_redirect_response=False)
