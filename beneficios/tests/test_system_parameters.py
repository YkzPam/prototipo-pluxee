from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from beneficios import parameters
from beneficios.forms_extra import PaymentForm
from beneficios.models import AuditEvent, BenefitAccount, Movement, SystemParameters
from beneficios.policies import session_policy


class SystemParametersTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.admin = users.create_user(username='gestor_parametros', is_staff=True)
        cls.beneficiary = users.create_user(username='titular_parametros', password='ClaveSegura#2026')

    def values(self, **changes):
        return {'registration_initial_credit': 30000, 'login_max_attempts': 3,
                'session_idle_minutes': 10, 'payment_max_amount': 2000, **changes}

    def test_defaults_come_from_settings_until_an_administrator_saves(self):
        active = parameters.current()
        self.assertEqual(active.registration_initial_credit, settings.REGISTRATION_INITIAL_CREDIT)
        self.assertEqual(active.login_max_attempts, settings.LOGIN_MAX_ATTEMPTS)
        self.assertEqual(active.session_idle_seconds, settings.SESSION_IDLE_SECONDS)
        self.assertEqual(active.payment_max_amount, parameters.PAYMENT_MAX_AMOUNT)
        self.assertFalse(SystemParameters.objects.exists())

    def test_administrator_saves_valid_values_and_the_log_lists_each_change(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('admin_parametros')).status_code, 200)
        response = self.client.post(reverse('admin_parametros'), self.values())
        self.assertRedirects(response, reverse('admin_parametros'))
        row = SystemParameters.objects.get()
        self.assertEqual((row.login_max_attempts, row.session_idle_minutes, row.updated_by), (3, 10, self.admin))
        event = AuditEvent.objects.get(event_type=AuditEvent.Type.SETTINGS)
        self.assertEqual(event.actor, self.admin)
        self.assertEqual(event.detail, 'Abono inicial: de $48.000 a $30.000; Intentos de ingreso: de 5 a 3; '
                                       'Inactividad (min): de 15 a 10; Máximo por compra: de $1.000.000 a $2.000')

        self.client.post(reverse('admin_parametros'), self.values())
        self.assertEqual(AuditEvent.objects.filter(event_type=AuditEvent.Type.SETTINGS).count(), 1)

    def test_out_of_range_values_are_rejected_without_saving(self):
        self.client.force_login(self.admin)
        for field, value in (('login_max_attempts', 1), ('session_idle_minutes', 600),
                             ('payment_max_amount', 5), ('registration_initial_credit', -1),
                             ('login_max_attempts', 'x')):
            with self.subTest(field=field, value=value):
                response = self.client.post(reverse('admin_parametros'), self.values(**{field: value}))
                self.assertEqual(response.status_code, 400)
        self.assertFalse(SystemParameters.objects.exists())

    def test_beneficiary_cannot_read_or_change_parameters(self):
        self.client.force_login(self.beneficiary)
        self.assertEqual(self.client.get(reverse('admin_parametros')).status_code, 403)
        self.assertEqual(self.client.post(reverse('admin_parametros'), self.values()).status_code, 403)
        self.assertFalse(SystemParameters.objects.exists())

    def test_saved_values_change_lockout_session_payment_and_registration(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('admin_parametros'), self.values(registration_initial_credit=0))
        self.client.logout()

        self.assertEqual(session_policy().idle_seconds, 600)
        amount = PaymentForm(data={'method': 'online', 'amount': 5000, 'pin': '4826'})
        self.assertIn('El monto máximo por compra es $2.000.', amount.errors['amount'])
        self.assertNotIn('amount', PaymentForm(data={'method': 'online', 'amount': 2000, 'pin': '4826'}).errors)

        for _ in range(3):
            self.client.post(reverse('ingresar'), {'username': 'titular_parametros', 'password': 'Incorrecta#1'})
        blocked = self.client.post(reverse('ingresar'), {'username': 'titular_parametros', 'password': 'ClaveSegura#2026'})
        self.assertEqual(blocked.status_code, 200)
        self.assertFalse(blocked.wsgi_request.user.is_authenticated)

        self.client.post(reverse('crear_usuario'), {
            'username': 'cuenta_sin_abono', 'first_name': 'Rosa', 'last_name': 'Parra',
            'password1': 'PortalSeguro49!', 'password2': 'PortalSeguro49!', 'pin': '4826'})
        account = BenefitAccount.objects.get(user__username='cuenta_sin_abono')
        self.assertFalse(Movement.objects.filter(account=account).exists())
