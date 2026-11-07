"""Cuentas y libro de movimientos ficticios, idempotente y sin borrar datos existentes."""
from datetime import datetime
from zoneinfo import ZoneInfo
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from beneficios.models import BenefitAccount, DemoCard, Merchant, Movement, ServiceState


class Command(BaseCommand):
    help = 'Prepara exclusivamente datos sintéticos para la demostración local.'

    @transaction.atomic
    def handle(self, *args, **options):
        user_model = get_user_model()
        fixtures = [
            ('beneficiario', 'Camila', 'Prueba', 'Beneficio de alimentación', '2026', False),
            ('beneficiario2', 'Diego', 'Prueba', 'Beneficio de alimentación', '4068', False),
            ('sinmovimientos', 'Alex', 'Prueba', 'Beneficio de alimentación', '8042', False),
            ('administrador', 'Administración', 'Académica', None, '', True),
        ]
        created_count = 0
        for username, first, last, label, suffix, staff in fixtures:
            user, created = user_model.objects.get_or_create(username=username, defaults={
                'first_name': first, 'last_name': last, 'is_staff': staff, 'is_active': True,
            })
            if created:
                # Clave pública de ejercicio; no se reutiliza para ningún sistema real.
                user.set_password('Prototipo2026!')
                user.must_change_password = True
                user.save(update_fields=['password', 'must_change_password'])
                created_count += 1
            if label:
                account, account_created = BenefitAccount.objects.get_or_create(
                    user=user, defaults={'public_label': label, 'number_suffix': suffix})
                if not DemoCard.objects.filter(account=account).exists():
                    DemoCard.objects.create(account=account, pin_hash=make_password('4826'))
                if account_created and username != 'sinmovimientos':
                    month = timezone.localdate().replace(day=1)
                    values = [('abono', 48000, 'Abono mensual de prueba', 1, 9),
                              ('cargo', 4200, 'Almacén de prueba', 2, 13),
                              ('cargo', 3650, 'Cafetería de prueba', 3, 12),
                              ('cargo', 7100, 'Supermercado de prueba', 4, 18),
                              ('cargo', 2800, 'Colación de prueba', 5, 14)]
                    if username == 'beneficiario2':
                        values = [('abono', 39000, 'Abono mensual de otra cuenta', 1, 9),
                                  ('cargo', 6900, 'Compra de otra cuenta', 4, 15)]
                    for kind, amount, desc, day, hour in values:
                        Movement.objects.create(account=account, kind=kind, amount=amount, description=desc,
                            occurred_at=datetime(month.year, month.month, day, hour, tzinfo=ZoneInfo('America/Santiago')))
        for code, label in [('balance', 'Saldo'), ('movements', 'Movimientos')]:
            ServiceState.objects.get_or_create(code=code, defaults={'label': label, 'available': True})
        merchants = [
            ('DEM001', 'Supermercado Demo', 'Supermercado', 'Santiago', 'Dirección ficticia 01, sin ubicación real', 'Productos de alimentación para el ejercicio académico.'),
            ('DEM002', 'Almacén Campus', 'Almacén', 'San Miguel', 'Dirección ficticia 02, sin ubicación real', 'Comercio inventado para probar búsqueda y favoritos.'),
            ('DEM003', 'Cafetería Aula', 'Cafetería', 'Santiago', 'Dirección ficticia 03, sin ubicación real', 'Cafetería ficticia para realizar pagos de demostración.'),
            ('DEM004', 'Colaciones del Estudiante', 'Restaurante', 'La Florida', 'Dirección ficticia 04, sin ubicación real', 'Local inventado, sin relación con una red de comercios real.'),
            ('DEM005', 'Verdulería de Prueba', 'Verdulería', 'San Miguel', 'Dirección ficticia 05, sin ubicación real', 'Comercio sintético del catálogo de demostración.'),
            ('DEM006', 'Panadería Taller', 'Panadería', 'La Florida', 'Dirección ficticia 06, sin ubicación real', 'Panadería ficticia para las funciones del prototipo.'),
        ]
        for code, name, category, commune, address, description in merchants:
            Merchant.objects.get_or_create(code=code, defaults={
                'name': name, 'category': category, 'commune': commune,
                'address': address, 'description': description, 'active': True})
        self.stdout.write(self.style.SUCCESS(f'Demostración preparada. Cuentas nuevas: {created_count}. No se modificaron cuentas existentes.'))
