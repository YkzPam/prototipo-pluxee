"""Datos del servidor que alimentan la identidad visual: categorías, totales por día, indicadores y secciones."""
import uuid
from datetime import datetime, timedelta, timezone as datetime_timezone

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import resolve, reverse
from django.utils import timezone

from beneficios.charts import sparkline
from beneficios.context_processors import greeting, portal_context
from beneficios.models import AuditEvent, BenefitAccount, Merchant, Movement, Payment, ServiceState
from beneficios.templatetags.merchant_visuals import merchant_cover, merchant_slug
from beneficios.views import _kpi_cards


class MovementVisualDataTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.owner = users.create_user(username='titular_visual')
        cls.account = BenefitAccount.objects.create(user=cls.owner, number_suffix='5150')
        ServiceState.objects.create(code='balance', label='Saldo')
        ServiceState.objects.create(code='movements', label='Movimientos')
        cafe = Merchant.objects.create(code='VIS-01', name='Café de prueba', category='Cafetería', commune='Santiago',
                                       address='Calle 1', description='Local de prueba')
        Merchant.objects.create(code='VIS-02', name='Panadería de prueba', category='Panadería', commune='Santiago',
                                address='Calle 2', description='Local de prueba')
        day = datetime(2026, 11, 3, 15, tzinfo=datetime_timezone.utc)
        cls.credit = Movement.objects.create(account=cls.account, kind='abono', amount=20000,
                                             description='Abono mensual', occurred_at=day - timedelta(hours=2))
        cls.paid = Movement.objects.create(account=cls.account, kind='cargo', amount=2500,
                                           description='Compra en Café de prueba', occurred_at=day)
        Payment.objects.create(user=cls.owner, account=cls.account, merchant=cafe, movement=cls.paid, amount=2500,
                               balance_after=17500, idempotency_key=uuid.uuid4())
        cls.by_name = Movement.objects.create(account=cls.account, kind='cargo', amount=1800,
                                              description='Compra en Panadería de prueba', occurred_at=day + timedelta(hours=1))
        cls.unknown = Movement.objects.create(account=cls.account, kind='cargo', amount=700,
                                              description='Compra sin comercio registrado', occurred_at=day + timedelta(days=1))

    def setUp(self):
        self.client.force_login(self.owner)

    def items(self):
        response = self.client.get(reverse('api_movimientos', args=[self.account.pk]))
        self.assertEqual(response.status_code, 200)
        return response.json()['data']

    def test_each_movement_carries_the_category_of_its_merchant(self):
        categories = {item['id']: item['category'] for item in self.items()['items']}
        self.assertEqual(categories[self.paid.pk], 'cafe')          # desde el pago registrado
        self.assertEqual(categories[self.by_name.pk], 'bakery')     # desde la descripción «Compra en …»
        self.assertEqual(categories[self.credit.pk], 'credit')
        self.assertEqual(categories[self.unknown.pk], 'other')

    def test_day_totals_add_credits_and_purchases_of_each_visible_day(self):
        totals = self.items()['day_totals']
        self.assertEqual(totals['2026-11-03'], {'credit': 20000, 'debit': 4300})
        self.assertEqual(totals['2026-11-04'], {'credit': 0, 'debit': 700})

    def test_day_totals_follow_the_type_filter(self):
        response = self.client.get(reverse('api_movimientos', args=[self.account.pk]), {'tipo': 'abono'})
        self.assertEqual(response.json()['data']['day_totals'], {'2026-11-03': {'credit': 20000, 'debit': 0}})

    def test_merchant_slug_ignores_accents_and_uses_a_default(self):
        self.assertEqual(merchant_slug('Verdulería'), 'produce')
        self.assertEqual(merchant_slug('VERDULERIA'), 'produce')
        self.assertEqual(merchant_slug('Ferretería'), 'grocery')
        self.assertEqual(merchant_cover('Cafetería'), 'img/merchant-cafe.svg')


class FollowupIndicatorTests(TestCase):
    def test_sparkline_uses_dot_decimals_and_marks_empty_series(self):
        line = sparkline([0, 2, 4, 1])
        self.assertFalse(line['empty'])
        self.assertRegex(line['line'], r'^\d+\.\d,\d+\.\d( \d+\.\d,\d+\.\d){3}$')
        self.assertTrue(line['area'].startswith('M') and line['area'].endswith('Z'))
        self.assertTrue(sparkline([0, 0, 0])['empty'])
        self.assertEqual(sparkline([]), {'empty': True})

    def test_indicators_compare_with_the_previous_24_hours_and_judge_the_direction(self):
        now = timezone.now()
        def event(event_type, outcome, hours_ago):
            created = AuditEvent.objects.create(event_type=event_type, outcome=outcome, detail='prueba',
                                                request_id=uuid.uuid4())
            AuditEvent.objects.filter(pk=created.pk).update(created_at=now - timedelta(hours=hours_ago))
        for hours in (1, 2, 3):
            event(AuditEvent.Type.LOGIN, AuditEvent.Outcome.DENIED, hours)
        event(AuditEvent.Type.LOGIN, AuditEvent.Outcome.DENIED, 30)
        event(AuditEvent.Type.LOGIN, AuditEvent.Outcome.SUCCESS, 1)
        event(AuditEvent.Type.LOGIN, AuditEvent.Outcome.SUCCESS, 26)
        event(AuditEvent.Type.LOGIN, AuditEvent.Outcome.SUCCESS, 27)
        stats = {'total': 4, 'success': 1, 'interrupted': 0, 'login_denied': 3, 'access_denied': 0, 'expired': 0}
        cards = {card['key']: card for card in _kpi_cards(stats, now)}
        self.assertEqual((cards['login_denied']['delta'], cards['login_denied']['tone']), (2, 'bad'))
        self.assertEqual((cards['success']['delta'], cards['success']['tone']), (-1, 'bad'))
        self.assertEqual(cards['total']['tone'], 'neutral')
        self.assertEqual(cards['expired']['tone'], 'neutral')
        self.assertFalse(cards['login_denied']['spark']['empty'])
        self.assertIn('outcome=denied', cards['login_denied']['query'])

    def test_followup_panel_shows_each_indicator_with_its_trend(self):
        admin = get_user_model().objects.create_user(username='gestor_visual', is_staff=True)
        self.client.force_login(admin)
        response = self.client.get(reverse('seguimiento'))
        self.assertContains(response, 'class="surface stat kpi-card', count=6)
        self.assertContains(response, 'que las 24&nbsp;h anteriores', count=6)


class PortalSectionTests(TestCase):
    def test_greeting_changes_with_the_hour(self):
        self.assertEqual([greeting(hour) for hour in (6, 13, 22, 3)],
                         ['Buenos días', 'Buenas tardes', 'Buenas noches', 'Buenas noches'])

    def test_each_page_belongs_to_a_section(self):
        factory = RequestFactory()
        for url, section in ((reverse('pagar'), 'pagos'), (reverse('admin_usuarios'), 'usuarios'),
                             (reverse('ayuda'), 'ayuda'), (reverse('ingresar'), 'general')):
            request = factory.get(url)
            request.resolver_match = resolve(url)
            self.assertEqual(portal_context(request)['portal_section'], section, url)
        self.assertEqual(portal_context(factory.get('/sin-ruta/'))['portal_section'], 'general')
