from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from beneficios.models import AuditEvent, BenefitAccount


class AccountActivityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.beneficiary = users.create_user(username='actividad_propia')
        cls.other = users.create_user(username='actividad_ajena')
        cls.administrator = users.create_user(username='actividad_admin', is_staff=True)
        BenefitAccount.objects.create(user=cls.beneficiary, number_suffix='1001')
        BenefitAccount.objects.create(user=cls.other, number_suffix='1002')

    def test_history_displays_only_the_owners_access_events_and_safe_reasons(self):
        event_types = AuditEvent.Type
        outcomes = AuditEvent.Outcome
        own_events = [
            (event_types.LOGIN, outcomes.SUCCESS, 'Texto interno de inicio'),
            (event_types.LOGOUT, outcomes.SUCCESS, 'Texto interno de salida'),
            (event_types.EXPIRED, outcomes.EXPIRED, 'La sesión finalizó por inactividad.'),
            (event_types.EXPIRED, outcomes.EXPIRED, 'La sesión alcanzó su duración máxima y requiere un nuevo ingreso.'),
            (event_types.EXPIRED, outcomes.EXPIRED, 'Detalle histórico no reconocido'),
            (event_types.LOGIN, outcomes.DENIED, 'Intento rechazado'),
            (event_types.PAYMENT, outcomes.SUCCESS, 'Pago de prueba'),
        ]
        own_events = [AuditEvent(actor=self.beneficiary, event_type=kind, outcome=outcome, detail=detail,
                                 request_id=uuid4()) for kind, outcome, detail in own_events]
        other_event = AuditEvent(actor=self.other, event_type=event_types.LOGOUT, outcome=outcomes.SUCCESS,
                                 detail='Sesión finalizada voluntariamente.', request_id=uuid4())
        AuditEvent.objects.bulk_create([*own_events, other_event])

        self.client.force_login(self.beneficiary)
        response = self.client.get(reverse('actividad_cuenta'), {'actor': self.other.pk})
        self.assertContains(response, 'Actividad de mi cuenta')
        self.assertEqual(response.context['page'].paginator.count, 5)
        for detail in ('Ingreso correcto.', 'La sesión se cerró voluntariamente.',
                       'La sesión finalizó por inactividad.', 'La sesión alcanzó su duración máxima.',
                       'Se registró el vencimiento de la sesión.'):
            self.assertContains(response, detail)
        self.assertNotContains(response, self.other.username)
        self.assertNotContains(response, 'Texto interno de inicio')
        self.assertNotContains(response, 'Detalle histórico no reconocido')
        for event in [*own_events, other_event]:
            self.assertNotContains(response, str(event.request_id))

    def test_history_is_paginated_and_linked_from_the_profile(self):
        AuditEvent.objects.bulk_create([
            AuditEvent(actor=self.beneficiary, event_type=AuditEvent.Type.LOGIN,
                       outcome=AuditEvent.Outcome.SUCCESS, detail='Ingreso correcto.', request_id=uuid4())
            for _ in range(21)
        ])
        self.client.force_login(self.beneficiary)
        url = reverse('actividad_cuenta')
        self.assertContains(self.client.get(reverse('perfil')), f'href="{url}"')
        first = self.client.get(url)
        self.assertEqual(len(first.context['activity']), 20)
        self.assertContains(first, 'href="?page=2"')
        second = self.client.get(url, {'page': 2})
        self.assertEqual(len(second.context['activity']), 1)
        self.assertContains(second, 'Página 2 de 2')

    def test_anonymous_and_staff_cannot_read_the_beneficiary_history(self):
        url = reverse('actividad_cuenta')
        self.assertRedirects(self.client.get(url), f"{reverse('ingresar')}?next={url}",
                             fetch_redirect_response=False)
        self.client.force_login(self.administrator)
        self.assertRedirects(self.client.get(url), reverse('seguimiento'), fetch_redirect_response=False)
