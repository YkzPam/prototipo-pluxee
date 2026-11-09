from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from beneficios.models import AuditEvent, ServiceInterruption, SupportReport


class SupportFollowupTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.beneficiary = users.create_user(username='beneficiaria.reportes')
        cls.other = users.create_user(username='beneficiario.ajeno')
        cls.admin = users.create_user(username='administrador.reportes', is_staff=True)

    def test_beneficiary_creates_report_and_can_only_read_own_reports(self):
        self.client.force_login(self.beneficiary)
        page = reverse('reportar_problema')
        description = 'Saldo pendiente <script>alert(1)</script>'
        result = self.client.post(page, {'category': 'balance', 'description': description})
        self.assertEqual(result.status_code, 302)
        report = SupportReport.objects.get(reporter=self.beneficiary)
        self.assertEqual(report.status, SupportReport.Status.RECEIVED)
        self.assertEqual(report.description, description)
        SupportReport.objects.create(reporter=self.other, category='session', description='Reporte privado ajeno')

        own_reports = self.client.get(page)
        self.assertContains(own_reports, str(report.pk))
        self.assertContains(own_reports, 'Saldo pendiente')
        self.assertNotContains(own_reports, 'Reporte privado ajeno')
        self.assertNotContains(own_reports, '<script>alert(1)</script>')
        with connection.cursor() as cursor:
            cursor.execute('SELECT description FROM beneficios_supportreport')
            stored_descriptions = [row[0] for row in cursor.fetchall()]
        self.assertTrue(all(value.startswith('enc:v1:') for value in stored_descriptions))

    def test_admin_filters_and_transitions_reports_without_overwriting_a_newer_state(self):
        report = SupportReport.objects.create(reporter=self.beneficiary, category='balance',
                                              description='Consulta de prueba de saldo')
        SupportReport.objects.create(reporter=self.other, category='session', description='Reporte sobre la sesión')
        inbox = reverse('reportes_admin')
        update = reverse('reportes_admin_actualizar', args=[report.pk])
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(inbox), 'Reporte sobre la sesión')
        filtered = self.client.get(inbox, {'categoria': 'balance', 'estado': 'received'})
        self.assertContains(filtered, 'Consulta de prueba de saldo')
        self.assertNotContains(filtered, 'Reporte sobre la sesión')

        self.client.post(update, {'status': 'resolved', 'response': 'Transición inválida'})
        report.refresh_from_db()
        self.assertEqual(report.status, 'received')
        self.client.post(update, {'status': 'review', 'response': 'Se revisó la consulta.'})
        self.client.post(update, {'status': 'review', 'response': 'Actualización repetida'})
        report.refresh_from_db()
        self.assertEqual(report.status, 'review')
        self.assertEqual(report.response, 'Se revisó la consulta.')
        self.client.post(update, {'status': 'resolved', 'response': 'La consulta volvió a responder.'})
        report.refresh_from_db()
        self.assertEqual(report.status, 'resolved')

        self.client.force_login(self.beneficiary)
        self.assertContains(self.client.get(reverse('reportar_problema')), 'La consulta volvió a responder.')
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(reverse('reportar_problema')), 'La consulta volvió a responder.')

    def test_updating_report_preserves_the_admin_inbox_page_and_filters(self):
        report = SupportReport.objects.create(reporter=self.beneficiary, category='balance',
                                              description='Reporte en la segunda página')
        SupportReport.objects.filter(pk=report.pk).update(created_at=timezone.now() - timedelta(days=1))
        for index in range(8):
            SupportReport.objects.create(reporter=self.beneficiary, category='balance',
                                         description=f'Reporte más reciente {index}')
        self.client.force_login(self.admin)
        query = {'categoria': 'balance', 'page': 2}
        update = reverse('reportes_admin_actualizar', args=[report.pk], query=query)
        response = self.client.post(update, {'status': 'review'}, follow=True)
        self.assertRedirects(response, reverse('reportes_admin', query=query, fragment='lista-reportes'))
        self.assertEqual(response.context['reports'].number, 2)
        self.assertContains(response, 'Reporte en la segunda página')

    def test_reports_require_authentication_authorization_and_csrf(self):
        report = SupportReport.objects.create(reporter=self.beneficiary, category='session', description='Sesión')
        page = reverse('reportar_problema')
        inbox = reverse('reportes_admin')
        update = reverse('reportes_admin_actualizar', args=[report.pk])
        self.assertEqual(self.client.get(page).status_code, 302)
        self.assertEqual(self.client.get(inbox).status_code, 302)
        self.client.force_login(self.beneficiary)
        self.assertEqual(self.client.get(inbox).status_code, 403)
        self.assertEqual(self.client.post(update, {'status': 'review'}).status_code, 403)
        report.refresh_from_db()
        self.assertEqual(report.status, 'received')

        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.beneficiary)
        self.assertEqual(strict.post(page, {'category': 'balance', 'description': 'Falta token'}).status_code, 403)
        strict.force_login(self.admin)
        self.assertEqual(strict.get(update).status_code, 405)
        self.assertEqual(strict.post(update, {'status': 'review'}).status_code, 403)

    def test_verification_note_requires_restoration_and_preserves_the_first_record(self):
        incident = ServiceInterruption.objects.create(service_code='balance', started_at=timezone.now())
        action = reverse('interrupcion_verificar', args=[incident.pk])
        self.client.force_login(self.beneficiary)
        self.assertEqual(self.client.post(action, {'verification_note': 'Verificación ajena'}).status_code, 403)
        self.client.force_login(self.admin)
        self.client.post(action, {'verification_note': 'Nota antes del restablecimiento'})
        incident.refresh_from_db()
        self.assertIsNone(incident.verified_at)

        incident.restored_at = timezone.now()
        incident.save(update_fields=['restored_at'])
        self.client.post(action, {'verification_note': '  '})
        incident.refresh_from_db()
        self.assertIsNone(incident.verified_at)
        note = 'Se reintentó el saldo y volvió a responder.'
        self.assertEqual(self.client.post(action, {'verification_note': note}).status_code, 302)
        self.client.post(action, {'verification_note': 'Segundo envío de la misma comprobación'})
        incident.refresh_from_db()
        self.assertEqual(incident.verification_note, note)
        self.assertEqual(incident.verified_by, self.admin)
        self.assertGreaterEqual(incident.verified_at, incident.restored_at)
        records = AuditEvent.objects.filter(event_type='service', actor=self.admin)
        self.assertEqual(records.count(), 1)
        self.assertNotIn(note, records.get().detail)
        self.assertEqual(incident.pending_queries.count(), 0)
        self.assertContains(self.client.get(reverse('seguimiento'), {'interruption': incident.pk}), note)
