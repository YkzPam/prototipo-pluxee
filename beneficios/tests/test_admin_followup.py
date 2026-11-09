import csv
from datetime import datetime, timedelta
from io import StringIO
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from beneficios.models import AuditEvent, ServiceInterruption


class AdminFollowupTests(TestCase):
    csv_header = ['Fecha y hora', 'Evento', 'Resultado', 'Duración (ms)']

    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.admin = users.create_user(username='admin.seguimiento', is_staff=True)
        cls.beneficiary = users.create_user(username='cuenta.no.exportable')

    def create_event(self, event_type, outcome, *, created_at=None, **values):
        with patch('django.utils.timezone.now', return_value=created_at or timezone.now()):
            return AuditEvent.objects.create(
                actor=self.beneficiary, event_type=event_type, outcome=outcome,
                detail='=Detalle de prueba excluido', request_id=uuid4(), **values,
            )

    def read_csv(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('text/csv'))
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('bitacora_pluxee.csv', response['Content-Disposition'])
        raw = b''.join(response.streaming_content) if response.streaming else response.content
        return list(csv.reader(StringIO(raw.decode('utf-8-sig'))))

    def test_detail_and_export_require_administrative_access(self):
        incident = ServiceInterruption.objects.create(service_code='balance', started_at=timezone.now())
        urls = [reverse('seguimiento'), reverse('seguimiento_exportar')]
        for url in urls:
            self.assertEqual(self.client.get(url, {'interruption': incident.pk}).status_code, 302)

        self.client.force_login(self.beneficiary)
        for url in urls:
            self.assertEqual(self.client.get(url, {'interruption': incident.pk}).status_code, 403)

        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(urls[1]).status_code, 405)

    def test_selected_interruption_and_csv_apply_the_same_filters(self):
        self.client.force_login(self.admin)
        now = timezone.now()
        first = ServiceInterruption.objects.create(service_code='balance', started_at=now - timedelta(days=4))
        second = ServiceInterruption.objects.create(service_code='balance', started_at=now - timedelta(days=1))
        older = self.create_event('balance', 'pending', interruption=first, duration_ms=15,
                                  created_at=now - timedelta(hours=3))
        latest = self.create_event('balance', 'pending', interruption=first, duration_ms=20)
        self.create_event('balance', 'pending', interruption=first, duration_ms=30,
                          created_at=now - timedelta(days=3))
        self.create_event('balance', 'pending', interruption=second, duration_ms=40)
        self.create_event('balance', 'success', duration_ms=50)
        filters = {'interruption': first.pk, 'event_type': 'balance', 'outcome': 'pending', 'period': '24h'}

        detail = self.client.get(reverse('seguimiento'), filters)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.context['selected_interruption'].pk, first.pk)
        self.assertEqual(list(detail.context['events']), [latest, older])

        rows = self.read_csv(self.client.get(reverse('seguimiento_exportar'), filters))
        self.assertEqual(rows[0], self.csv_header)
        self.assertIsNotNone(datetime.fromisoformat(rows[1][0]).tzinfo)
        self.assertEqual([row[1:] for row in rows[1:]], [
            ['Consulta de saldo', 'Pendiente', '20'], ['Consulta de saldo', 'Pendiente', '15'],
        ])
        for value in (self.beneficiary.username, latest.detail, str(latest.request_id)):
            self.assertFalse(any(value in cell for row in rows for cell in row))

    def test_invalid_incident_is_not_an_unfiltered_request_and_empty_incident_has_headers(self):
        self.client.force_login(self.admin)
        empty = ServiceInterruption.objects.create(service_code='movements', started_at=timezone.now())
        for invalid in ('x', '-1', str(empty.pk + 1)):
            for name in ('seguimiento', 'seguimiento_exportar'):
                with self.subTest(route=name, interruption=invalid):
                    self.assertEqual(self.client.get(reverse(name), {'interruption': invalid}).status_code, 404)

        rows = self.read_csv(self.client.get(reverse('seguimiento_exportar'), {'interruption': empty.pk}))
        self.assertEqual(rows, [self.csv_header])

    def test_summary_metrics_and_links_exclude_unrelated_events_and_old_events(self):
        self.client.force_login(self.admin)
        balance = self.create_event('balance', 'pending')
        movements = self.create_event('movements', 'pending')
        login = self.create_event('login', 'denied')
        access = self.create_event('access', 'denied')
        expired = self.create_event('expired', 'expired')
        self.create_event('payment', 'pending')
        self.create_event('payment', 'denied')
        self.create_event('logout', 'success')
        self.create_event('login', 'denied', created_at=timezone.now() - timedelta(hours=25))

        url = reverse('seguimiento')
        response = self.client.get(url)
        expected_stats = {'total': 8, 'success': 1, 'interrupted': 2, 'login_denied': 1,
                          'access_denied': 1, 'expired': 1}
        for name, expected in expected_stats.items():
            with self.subTest(metric=name):
                self.assertEqual(response.context['stats'][name], expected)

        expected_links = {'interrupted': [movements, balance], 'login_denied': [login],
                          'access_denied': [access], 'expired': [expired]}
        for name, expected in expected_links.items():
            with self.subTest(link=name):
                selected = self.client.get(f'{url}?{response.context["summary_filters"][name]}')
                self.assertEqual(list(selected.context['events']), expected)

    def test_export_includes_matching_records_beyond_the_visible_page(self):
        self.client.force_login(self.admin)
        noon = timezone.localtime().replace(hour=12, minute=0, second=0, microsecond=0)
        self.create_event('movements', 'success', created_at=noon - timedelta(days=2))
        for duration in range(26):
            self.create_event('movements', 'success', duration_ms=duration,
                              created_at=noon + timedelta(seconds=duration))
        today = noon.date().isoformat()
        filters = {'event_type': 'movements', 'from_date': today, 'to_date': today}

        result = self.client.get(reverse('seguimiento'), filters)
        self.assertEqual(len(result.context['events']), 25)
        self.assertEqual(result.context['events'].paginator.count, 26)
        rows = self.read_csv(self.client.get(reverse('seguimiento_exportar'), filters))
        self.assertEqual([row[3] for row in rows[1:]], [str(value) for value in reversed(range(26))])

    def test_export_refuses_invalid_date_filters(self):
        self.client.force_login(self.admin)
        url = reverse('seguimiento_exportar')
        for filters in ({'from_date': 'x'}, {'from_date': '2026-11-08', 'to_date': '2026-11-07'}):
            with self.subTest(filters=filters):
                self.assertEqual(self.client.get(url, filters).status_code, 400)
