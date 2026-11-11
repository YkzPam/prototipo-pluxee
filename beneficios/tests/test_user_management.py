from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from beneficios.models import AuditEvent, BenefitAccount, Movement, ServiceState


class UserManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for code, label in (('balance', 'Saldo'), ('movements', 'Movimientos')):
            ServiceState.objects.create(code=code, label=label)
        User = get_user_model()
        cls.admin = User.objects.create_user(username='gestor_usuarios', is_staff=True)
        cls.other_admin = User.objects.create_user(username='gestor_secundario', is_staff=True)
        cls.beneficiary = User.objects.create_user(username='beneficiaria_control')
        # El alta pública crea usuario, cuenta, tarjeta y abono inicial como en la demostración.
        Client().post(reverse('crear_usuario'), {
            'username': 'cuenta_gestion', 'first_name': 'Lucia', 'last_name': 'Gestion',
            'password1': 'PortalSeguro49!', 'password2': 'PortalSeguro49!', 'pin': '4826'})
        cls.target = User.objects.get(username='cuenta_gestion')
        cls.account = BenefitAccount.objects.get(user=cls.target)

    def detail_url(self, user=None):
        return reverse('admin_usuario', args=[(user or self.target).pk])

    def post_action(self, action, **fields):
        data = {'action': action, **{f'{action}-{name}': value for name, value in fields.items()}}
        return self.client.post(self.detail_url(), data)

    def test_list_filters_by_username_and_state(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('admin_usuarios'), {'q': 'gestion', 'estado': 'active'})
        listed = [user.username for user in response.context['users']]
        self.assertEqual(listed, ['cuenta_gestion'])
        # Las cuentas administrativas nunca aparecen en el listado de beneficiarios.
        listed = [user.username for user in self.client.get(reverse('admin_usuarios')).context['users']]
        self.assertNotIn('gestor_secundario', listed)
        self.assertIn('beneficiaria_control', listed)
        response = self.client.get(reverse('admin_usuarios'), {'estado': 'inactive'})
        self.assertEqual(list(response.context['users']), [])

    def test_staff_accounts_are_not_managed_from_user_detail(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.detail_url(self.other_admin)).status_code, 404)

    def test_profile_edit_is_validated_and_audited(self):
        self.client.force_login(self.admin)
        response = self.post_action('profile', first_name='<script>', last_name='Gestion')
        self.assertEqual(response.status_code, 200)
        self.target.refresh_from_db()
        self.assertEqual(self.target.first_name, 'Lucia')
        self.assertRedirects(self.post_action('profile', first_name='Lucía', last_name='Editada'), self.detail_url())
        self.target.refresh_from_db()
        self.assertEqual((self.target.first_name, self.target.last_name), ('Lucía', 'Editada'))
        self.assertTrue(AuditEvent.objects.filter(actor=self.admin, target=self.target,
                                                  detail='Nombre y apellido actualizados.').exists())

    def test_admin_reset_assigns_temporary_password_that_must_be_changed(self):
        beneficiary_session = self.client_class()
        beneficiary_session.post(reverse('ingresar'), {'username': 'cuenta_gestion', 'password': 'PortalSeguro49!'})
        self.assertEqual(beneficiary_session.get(reverse('api_saldo', args=[self.account.pk])).status_code, 200)

        self.client.force_login(self.admin)
        response = self.post_action('password', password1='Temporal#2026x', password2='Temporal#2026x')
        self.assertRedirects(response, self.detail_url())
        self.target.refresh_from_db()
        self.assertTrue(self.target.must_change_password)
        self.assertTrue(AuditEvent.objects.filter(target=self.target, detail='Contraseña temporal asignada.').exists())

        # La sesión abierta antes del restablecimiento deja de ser válida.
        self.assertEqual(beneficiary_session.get(reverse('api_saldo', args=[self.account.pk])).status_code, 401)

        # Con la clave temporal solo se permite cambiarla.
        temporary = self.client_class()
        response = temporary.post(reverse('ingresar'), {'username': 'cuenta_gestion', 'password': 'Temporal#2026x'})
        self.assertRedirects(response, reverse('cambiar_clave'), fetch_redirect_response=False)
        self.assertRedirects(temporary.get(reverse('inicio')), reverse('cambiar_clave'), fetch_redirect_response=False)
        api = temporary.get(reverse('api_saldo', args=[self.account.pk]))
        self.assertEqual(api.json()['status'], 'password_change_required')

        response = temporary.post(reverse('cambiar_clave'), {
            'old_password': 'Temporal#2026x', 'new_password1': 'Definitiva#2027y', 'new_password2': 'Definitiva#2027y',
        })
        self.assertRedirects(response, reverse('inicio'), fetch_redirect_response=False)
        self.target.refresh_from_db()
        self.assertFalse(self.target.must_change_password)
        self.assertEqual(temporary.get(reverse('api_saldo', args=[self.account.pk])).status_code, 200)

    def test_weak_or_mismatched_reset_password_is_rejected(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.post_action('password', password1='corta', password2='corta').status_code, 200)
        self.assertEqual(self.post_action('password', password1='Temporal#2026x', password2='Otra#2026x').status_code, 200)
        self.target.refresh_from_db()
        self.assertFalse(self.target.must_change_password)
        self.assertTrue(self.target.check_password('PortalSeguro49!'))

    def test_deactivation_requires_confirmation_and_closes_sessions(self):
        beneficiary_session = self.client_class()
        beneficiary_session.post(reverse('ingresar'), {'username': 'cuenta_gestion', 'password': 'PortalSeguro49!'})
        self.client.force_login(self.admin)

        self.assertEqual(self.post_action('state', state='inactive').status_code, 200)
        self.target.refresh_from_db()
        self.assertTrue(self.target.is_active)

        response = self.client.post(self.detail_url(), {
            'action': 'state', 'state-state': 'inactive', 'confirm_deactivation': '1'})
        self.assertRedirects(response, self.detail_url())
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_active)
        self.assertEqual(beneficiary_session.get(reverse('api_saldo', args=[self.account.pk])).status_code, 401)
        login = self.client_class().post(reverse('ingresar'), {'username': 'cuenta_gestion', 'password': 'PortalSeguro49!'})
        self.assertEqual(login.status_code, 200)

        self.assertRedirects(self.post_action('state', state='active'), self.detail_url())
        self.target.refresh_from_db()
        self.assertTrue(self.target.is_active)

    def test_credit_is_idempotent_and_requires_active_account(self):
        self.client.force_login(self.admin)
        before = Movement.objects.filter(account=self.account, kind=Movement.Kind.CREDIT).count()
        reference = str(uuid4())
        for _ in range(2):
            self.post_action('credit', amount='5000', reference=reference)
        self.assertEqual(Movement.objects.filter(account=self.account, kind=Movement.Kind.CREDIT).count(), before + 1)
        response = self.post_action('credit', amount='7000', reference=reference)
        self.assertContains(response, 'Esa referencia ya se utilizó')

        get_user_model().objects.filter(pk=self.target.pk).update(is_active=False)
        response = self.post_action('credit', amount='5000', reference=str(uuid4()))
        self.assertContains(response, 'El abono requiere una cuenta de beneficio activa.')
        self.assertEqual(Movement.objects.filter(account=self.account, kind=Movement.Kind.CREDIT).count(), before + 1)

    def test_unknown_action_changes_nothing(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.detail_url(), {'action': 'is_staff', 'is_staff': '1'})
        self.assertEqual(response.status_code, 200)
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_staff)

    def test_beneficiary_cannot_reach_user_administration(self):
        self.client.force_login(self.beneficiary)
        for url in (reverse('admin_usuarios'), reverse('admin_crear_usuario'), self.detail_url()):
            self.assertEqual(self.client.get(url).status_code, 403)
        response = self.client.post(self.detail_url(), {
            'action': 'password', 'password-password1': 'Temporal#2026x', 'password-password2': 'Temporal#2026x'})
        self.assertEqual(response.status_code, 403)
        self.target.refresh_from_db()
        self.assertTrue(self.target.check_password('PortalSeguro49!'))
        self.assertTrue(AuditEvent.objects.filter(actor=self.beneficiary, event_type=AuditEvent.Type.ACCESS,
                                                  outcome=AuditEvent.Outcome.DENIED).exists())

    def test_table_shows_balance_card_and_sorts_by_signup(self):
        Movement.objects.create(account=self.account, kind=Movement.Kind.DEBIT, amount=1500,
                                description='Compra en Café Alameda', occurred_at=self.target.date_joined)
        self.client.force_login(self.admin)
        response = self.client.get(reverse('admin_usuarios'), {'q': 'cuenta_gestion'})
        row = response.context['users'][0]
        credited = sum(m.amount for m in Movement.objects.filter(account=self.account, kind=Movement.Kind.CREDIT))
        self.assertEqual(row.balance, credited - 1500)
        self.assertFalse(row.card_blocked)
        newest = self.client.get(reverse('admin_usuarios'), {'orden': 'alta'})
        self.assertEqual(newest.context['users'][0].username, 'cuenta_gestion')
        self.assertEqual(self.client.get(reverse('admin_usuarios'), {'orden': 'x'}).context['order'], 'usuario')

    def test_administrator_blocks_and_activates_the_card_with_audit(self):
        self.client.force_login(self.admin)
        self.assertRedirects(self.post_action('card', state='block'), self.detail_url())
        self.account.demo_card.refresh_from_db()
        self.assertTrue(self.account.demo_card.is_blocked)
        self.assertTrue(AuditEvent.objects.filter(target=self.target, detail='Tarjeta bloqueada por administración.').exists())
        self.assertContains(self.client.get(self.detail_url()), 'Activar tarjeta')
        self.assertRedirects(self.post_action('card', state='unblock'), self.detail_url())
        self.account.demo_card.refresh_from_db()
        self.assertFalse(self.account.demo_card.is_blocked)

        self.client.force_login(self.beneficiary)
        self.assertEqual(self.post_action('card', state='block').status_code, 403)
        self.account.demo_card.refresh_from_db()
        self.assertFalse(self.account.demo_card.is_blocked)

    def test_anonymous_user_is_sent_to_login(self):
        response = self.client.get(reverse('admin_usuarios'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith(reverse('ingresar')))
