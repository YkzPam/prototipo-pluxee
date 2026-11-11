from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from beneficios.models import BenefitAccount, Merchant, Movement, Notification, ServiceState


class RegistrationCreditTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for code, label in (('balance', 'Saldo'), ('movements', 'Movimientos')):
            ServiceState.objects.create(code=code, label=label)
        cls.admin = get_user_model().objects.create_user(username='gestor_alta', is_staff=True)
        cls.merchant = Merchant.objects.create(
            code='ALTA001', name='Comercio de control', category='Almacén', commune='Santiago',
            address='Dirección de control', description='Comercio para verificar el abono',
        )

    def values(self):
        return {'username': 'cuenta_nueva', 'first_name': 'Elena', 'last_name': 'Cuenta',
                'password1': 'PortalSeguro49!', 'password2': 'PortalSeguro49!', 'pin': '4826'}

    def assert_initial_credit(self, username):
        user = get_user_model().objects.get(username=username)
        account = BenefitAccount.objects.get(user=user)
        credit = Movement.objects.get(account=account)
        self.assertEqual((credit.kind, credit.amount, credit.description),
                         (Movement.Kind.CREDIT, settings.REGISTRATION_INITIAL_CREDIT, 'Abono inicial'))
        self.assertEqual(Notification.objects.filter(user=user, kind=Notification.Kind.CREDIT).count(), 1)
        return user, account

    def test_public_signup_receives_one_credit_even_after_duplicate_submission(self):
        self.assertRedirects(self.client.post(reverse('crear_usuario'), self.values()),
                             reverse('registro_completado'))
        user, account = self.assert_initial_credit('cuenta_nueva')
        self.assertFalse(user.is_staff)
        self.assertContains(self.client.get(reverse('registro_completado')), '48.000')
        self.assertEqual(self.client.post(reverse('crear_usuario'), self.values()).status_code, 200)
        self.assertEqual(Movement.objects.filter(account=account).count(), 1)

    def test_admin_signup_receives_the_same_credit(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('admin_crear_usuario'), self.values())
        user, _ = self.assert_initial_credit('cuenta_nueva')
        self.assertRedirects(response, reverse('admin_usuario', args=[user.pk]))

    def test_audit_failure_rolls_back_user_credit_and_notification(self):
        before = Notification.objects.count()
        movements_before = Movement.objects.count()
        with patch('beneficios.views_users.record', return_value=False):
            response = self.client.post(reverse('crear_usuario'), self.values())
        self.assertEqual(response.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(username='cuenta_nueva').exists())
        self.assertEqual(Movement.objects.count(), movements_before)
        self.assertEqual(Notification.objects.count(), before)

    def test_new_user_can_pay_using_the_initial_credit(self):
        self.client.post(reverse('crear_usuario'), self.values())
        user, account = self.assert_initial_credit('cuenta_nueva')
        self.client.post(reverse('ingresar'), {'username': user.username, 'password': self.values()['password1']})
        response = self.client.get(reverse('api_saldo', args=[account.pk]))
        self.assertEqual(response.json()['data']['balance'], settings.REGISTRATION_INITIAL_CREDIT)
        payment = {'method': 'qr', 'qr_code': self.merchant.code, 'amount': 1000, 'pin': '4826',
                   'idempotency_key': str(uuid4()), 'payment_step': 'review'}
        self.assertEqual(self.client.post(reverse('pagar'), payment).status_code, 302)
        self.assertEqual(Movement.objects.filter(account=account).count(), 1)
        token = next(iter(self.client.session['payment_reviews']))
        self.assertEqual(self.client.post(reverse('pagar'), {
            'payment_step': 'confirm', 'review_token': token,
        }).status_code, 302)
        response = self.client.get(reverse('api_saldo', args=[account.pk]))
        self.assertEqual(response.json()['data']['balance'], settings.REGISTRATION_INITIAL_CREDIT - 1000)
