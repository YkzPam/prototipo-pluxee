import json
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from beneficios.models import BenefitAccount


class SessionWarningTests(TestCase):
    password = 'ClaveDePrueba2026!'

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username='sesion-prueba', password=cls.password)
        BenefitAccount.objects.create(user=cls.user, number_suffix='7788')

    def login(self, target=''):
        return self.client.post(reverse('ingresar'), {
            'username': self.user.username,
            'password': self.password,
            'next': target,
        })

    def test_passive_clock_does_not_renew_and_activity_preserves_absolute_deadline(self):
        self.login()
        session = self.client.session
        session['last_activity_at'] = (timezone.now() - timedelta(seconds=settings.SESSION_IDLE_SECONDS - 30)).timestamp()
        last_activity = session['last_activity_at']
        session.save()

        passive = self.client.get(reverse('actividad'))
        self.assertEqual(passive.status_code, 200)
        clock = json.loads(passive['X-Session-Clock'])
        self.assertLess(clock['idle'] - clock['now'], clock['warning'])
        self.assertEqual(self.client.session['last_activity_at'], last_activity)

        continued = self.client.post(reverse('actividad'))
        self.assertEqual(continued.status_code, 200)
        renewed = json.loads(continued['X-Session-Clock'])
        self.assertGreater(renewed['idle'], clock['idle'])
        self.assertEqual(renewed['absolute'], clock['absolute'])
        self.assertGreater(self.client.session['last_activity_at'], last_activity)

    def test_expiry_preserves_only_valid_filters_from_read_view(self):
        self.login()
        session = self.client.session
        session['last_activity_at'] = timezone.now().timestamp() - settings.SESSION_IDLE_SECONDS - 1
        session.save()
        movement_url = reverse('movimientos')
        result = self.client.get(movement_url, {
            'desde': '2026-11-01', 'hasta': '2026-11-07', 'tipo': 'cargo', 'page': 2, 'extra': 'desconocido',
        })
        login_url = urlsplit(result['Location'])
        target = parse_qs(login_url.query)['next'][0]
        self.assertEqual(login_url.path, reverse('ingresar'))
        self.assertEqual(target, movement_url + '?desde=2026-11-01&hasta=2026-11-07&tipo=cargo&page=2')
        self.assertRedirects(self.login(target), target, fetch_redirect_response=False)

    def test_reauthentication_cannot_resume_payment_or_invalid_filter(self):
        self.assertRedirects(self.login(reverse('pagar') + '?pin=4826'), reverse('inicio'),
                             fetch_redirect_response=False)
        self.client.post(reverse('salir'))
        movements = reverse('movimientos')
        self.assertRedirects(self.login(movements + '?tipo=no-existe'), movements, fetch_redirect_response=False)
