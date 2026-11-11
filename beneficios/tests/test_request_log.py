from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from beneficios.models import BenefitAccount


class RequestLogTests(TestCase):
    """Registro en terminal de cada página atendida, sin datos personales ni parámetros."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username='titular_registro')
        BenefitAccount.objects.create(user=cls.owner, number_suffix='4411')

    def test_each_page_is_logged_with_method_path_status_and_profile_only(self):
        self.client.force_login(self.owner)
        with self.assertLogs('beneficios.peticiones', level='INFO') as logs:
            self.client.get(reverse('inicio') + '?nombre=secreto')
        line = logs.output[-1]
        self.assertIn('GET', line)
        self.assertIn(reverse('inicio'), line)
        self.assertIn('200', line)
        self.assertIn(f'beneficiario #{self.owner.pk}', line)
        self.assertNotIn('secreto', line)
        self.assertNotIn('titular_registro', line)

    def test_visitor_redirect_is_logged(self):
        with self.assertLogs('beneficios.peticiones', level='INFO') as logs:
            self.client.get(reverse('inicio'))
        self.assertIn('302', logs.output[-1])
        self.assertIn('visitante', logs.output[-1])

    def test_static_files_and_session_polling_are_not_logged(self):
        self.client.force_login(self.owner)
        with self.assertNoLogs('beneficios.peticiones', level='INFO'):
            self.client.get(reverse('actividad'))
            self.client.get('/static/css/fluidez.css')
