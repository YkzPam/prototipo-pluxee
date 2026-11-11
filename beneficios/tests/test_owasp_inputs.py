from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from beneficios.forms_admin_incidents import IncidentManagementForm
from beneficios.forms_admin_merchants import MerchantFilterForm, MerchantForm
from beneficios.forms_admin_reports import MovementReportForm
from beneficios.forms_extra import MerchantSearchForm, PaymentForm, ProfileForm
from beneficios.forms_support import SupportReportForm, SupportReportUpdateForm
from beneficios.forms_users import AccountFilterForm, RegistrationForm
from beneficios.models import BenefitAccount, HelpTopic, MerchantCategory, SupportReport
from beneficios.validators import reject_dangerous_characters
from beneficios.views_restoration import VerificationNoteForm

# Caracteres que la pauta OWASP del curso pide rechazar, más el carácter nulo.
DANGEROUS = ['<', '>', '"', "'", '%', '(', ')', '&', '+', chr(92), chr(0)]


class DangerousCharacterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.admin = users.create_user(username='gestor_entradas', is_staff=True)
        cls.owner = users.create_user(username='titular_entradas')
        BenefitAccount.objects.create(user=cls.owner, number_suffix='7788')

    def test_validator_rejects_each_listed_character_and_accepts_plain_spanish_text(self):
        for character in DANGEROUS:
            with self.subTest(character=repr(character)):
                with self.assertRaises(ValidationError):
                    reject_dangerous_characters(f'texto {character} final')
        reject_dangerous_characters('Ñuñoa, José Pérez: saldo $2.500 a las 10:30; ¿ok? sí.')

    def test_every_free_text_field_applies_the_validator(self):
        report = SupportReport.objects.create(reporter=self.owner, category='other', description='Consulta')
        bad = 'Revisé el saldo (10:30)'
        forms = {
            'reporte del beneficiario': SupportReportForm({'category': 'other', 'description': bad}),
            'respuesta en la bandeja': SupportReportUpdateForm({'status': 'review', 'response': bad}),
            'respuesta de la incidencia': IncidentManagementForm(
                {'status': 'review', 'priority': 'normal', 'response': bad}, report=report),
            'nota de restablecimiento': VerificationNoteForm({'verification_note': bad}),
            'nombre del comercio': MerchantForm({'code': 'C9001', 'name': '<script>', 'category': 'Otro',
                                                 'commune': 'Maipú', 'address': 'Calle 1', 'description': 'x'}),
            'dirección del comercio': MerchantForm({'code': 'C9002', 'name': 'Local', 'category': 'Otro',
                                                    'commune': 'Maipú', 'address': "Av. O'Higgins 1", 'description': 'x'}),
            'búsqueda de comercios (admin)': MerchantFilterForm({'q': 'a&b'}),
            'búsqueda de comercios': MerchantSearchForm({'q': "D'Rosa"}),
            'búsqueda de usuarios': AccountFilterForm({'q': 'a+b'}),
            'usuario en informes': MovementReportForm({'desde': '2026-11-01', 'hasta': '2026-11-02', 'usuario': 'a"b'}),
            'código QR': PaymentForm({'method': 'qr', 'qr_code': 'C1%01', 'amount': 100, 'pin': '4826'}),
            'nombre del perfil': ProfileForm({'first_name': "O'Brien", 'last_name': 'Paz'}),
            'usuario nuevo con +': RegistrationForm({'username': 'ana+1', 'first_name': 'Ana', 'last_name': 'Paz',
                                                    'password1': 'ClaveSegura#2026', 'password2': 'ClaveSegura#2026',
                                                    'pin': '1234'}),
        }
        for name, form in forms.items():
            with self.subTest(campo=name):
                self.assertFalse(form.is_valid())

    def test_report_with_dangerous_characters_is_not_saved(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse('reportar_problema'), {
            'category': 'balance', 'description': 'El saldo <b>no</b> cambió'})
        self.assertContains(response, 'No se admiten los caracteres', status_code=400)
        self.assertFalse(SupportReport.objects.exists())
        ok = self.client.post(reverse('reportar_problema'), {
            'category': 'balance', 'description': 'El saldo no cambió después de pagar en Ñuñoa.'})
        self.assertEqual(ok.status_code, 302)
        self.assertEqual(SupportReport.objects.count(), 1)


class CatalogTablesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user(username='gestor_tablas', is_staff=True)
        cls.owner = get_user_model().objects.create_user(username='titular_tablas')
        BenefitAccount.objects.create(user=cls.owner, number_suffix='9900')

    def test_merchant_categories_come_from_the_table(self):
        self.assertTrue(MerchantCategory.objects.filter(name='Supermercado').exists())
        MerchantCategory.objects.create(name='Feria libre', position=50)
        MerchantCategory.objects.filter(name='Otro').update(active=False)
        choices = [value for value, _ in MerchantForm().fields['category'].choices if value]
        self.assertIn('Feria libre', choices)
        self.assertNotIn('Otro', choices)
        form = MerchantForm({'code': 'C9101', 'name': 'Feria Central', 'category': 'Feria libre',
                             'commune': 'Maipú', 'address': 'Calle 2', 'description': 'Frutas'})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertFalse(MerchantForm({'code': 'C9102', 'name': 'Local', 'category': 'Inventada',
                                       'commune': 'Maipú', 'address': 'Calle 3', 'description': 'x'}).is_valid())

    def test_help_page_lists_active_topics_from_the_table(self):
        self.assertEqual(HelpTopic.objects.count(), 6)
        HelpTopic.objects.create(question='¿Dónde veo mis comprobantes?', answer='En Mis movimientos.', position=10)
        HelpTopic.objects.filter(position=0).update(active=False)
        hidden = HelpTopic.objects.get(position=0).question
        self.client.force_login(self.owner)
        response = self.client.get(reverse('ayuda'))
        self.assertContains(response, '¿Dónde veo mis comprobantes?')
        self.assertNotContains(response, hidden)
