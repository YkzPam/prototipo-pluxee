from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from beneficios.charts import bar_chart
from beneficios.models import AuditEvent, BenefitAccount, Movement


class ChartTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.admin = users.create_user(username='gestor_graficos', is_staff=True)
        cls.owner = users.create_user(username='titular_graficos')
        cls.account = BenefitAccount.objects.create(user=cls.owner, number_suffix='5566')

    def event(self, outcome, created_at):
        with patch('django.utils.timezone.now', return_value=created_at):
            AuditEvent.objects.create(actor=self.owner, event_type='balance', outcome=outcome,
                                      detail='Consulta', request_id=uuid4())

    def test_bar_chart_scales_stacks_and_omits_empty_bars(self):
        chart = bar_chart(['a', 'b', 'c'], [('Uno', 'bar-success', [3, 0, 1]), ('Dos', 'bar-alert', [4, 0, 0])],
                          stacked=True)
        self.assertEqual(chart['y_ticks'][-1]['text'], '10')
        self.assertEqual(len(chart['bars']), 3)
        self.assertEqual([total for _, _, total in chart['legend']], [4, 4])
        self.assertTrue(bar_chart(['a'], [('Uno', 'bar-success', [0])])['empty'])

    def test_panel_counts_events_per_hour_in_the_last_day(self):
        now = timezone.now()
        self.event('success', now)
        self.event('denied', now)
        self.event('success', now - timedelta(hours=2))
        self.event('success', now - timedelta(hours=30))
        self.client.force_login(self.admin)
        chart = self.client.get(reverse('seguimiento')).context['hourly_chart']
        self.assertEqual([(name, total) for name, _, total in chart['legend']],
                         [('Correctos', 2), ('Rechazados o pendientes', 1)])
        self.assertEqual(len(chart['x_labels']), 8)

    def test_report_chart_totals_match_the_filtered_movements(self):
        today = timezone.localdate()
        noon = timezone.localtime().replace(hour=12, minute=0, second=0, microsecond=0)
        Movement.objects.create(account=self.account, kind='abono', amount=40000, description='Abono mensual Junaeb',
                                occurred_at=noon)
        Movement.objects.create(account=self.account, kind='cargo', amount=3500, description='Compra en Café Alameda',
                                occurred_at=noon)
        self.client.force_login(self.admin)
        response = self.client.get(reverse('admin_informes'), {'desde': today.isoformat(), 'hasta': today.isoformat()})
        self.assertEqual(response.status_code, 200)
        chart = response.context['movement_chart']
        self.assertEqual([(name, total) for name, _, total in chart['legend']], [('Abonos', 40000), ('Compras', 3500)])
        self.assertEqual(response.context['chart_bucket'], 'día')
        self.assertContains(response, '<svg viewBox="0 0 720 220"')
        # La configuración es-CL usa coma decimal; las coordenadas SVG deben conservar el punto.
        svg = response.content.decode()
        self.assertNotRegex(svg, r'\s(x|y|x1|x2|y1|y2|width|height)="[^"]*,')
        self.assertRegex(svg, r'<rect class="bar-chart-bar bar-success" x="\d+\.\d"')

        long_period = self.client.get(reverse('admin_informes'), {
            'desde': (today - timedelta(days=120)).isoformat(), 'hasta': today.isoformat()})
        self.assertEqual(long_period.context['chart_bucket'], 'semana')
