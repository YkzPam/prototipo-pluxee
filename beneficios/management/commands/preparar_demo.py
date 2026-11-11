"""Cuentas y libro de movimientos ficticios, idempotente y sin borrar datos existentes."""
from datetime import datetime
from zoneinfo import ZoneInfo
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from beneficios.demo_credentials import ADMIN_PASSWORD, BENEFICIARY_PASSWORD
from beneficios.demo_catalog import DEMO_MERCHANTS
from beneficios.models import BenefitAccount, DemoCard, Merchant, Movement, ServiceState


class Command(BaseCommand):
    help = 'Prepara exclusivamente datos sintéticos para la demostración local.'

    @transaction.atomic
    def handle(self, *args, **options):
        user_model = get_user_model()
        fixtures = [
            ('beneficiario', 'Camila', 'Rojas', 'Beneficio de alimentación', '2026', False),
            ('beneficiario2', 'Diego', 'Muñoz', 'Beneficio de alimentación', '4068', False),
            ('sinmovimientos', 'Alex', 'Soto', 'Beneficio de alimentación', '8042', False),
            ('administrador', 'Administración', 'Académica', None, '', True),
        ]
        created_count = 0
        for username, first, last, label, suffix, staff in fixtures:
            user, created = user_model.objects.get_or_create(username=username, defaults={
                'first_name': first, 'last_name': last, 'is_staff': staff, 'is_active': True,
            })
            if created:
                # Clave pública de ejercicio; no se reutiliza para ningún sistema real.
                user.set_password(ADMIN_PASSWORD if staff else BENEFICIARY_PASSWORD)
                user.save(update_fields=['password'])
                created_count += 1
            if label:
                account, account_created = BenefitAccount.objects.get_or_create(
                    user=user, defaults={'public_label': label, 'number_suffix': suffix})
                if not DemoCard.objects.filter(account=account).exists():
                    DemoCard.objects.create(account=account, pin_hash=make_password('4826'))
                if account_created and username != 'sinmovimientos':
                    month = timezone.localdate().replace(day=1)
                    values = [('abono', 48000, 'Abono mensual Junaeb', 1, 9),
                              ('cargo', 4200, 'Compra en Almacén Doña Rosa', 2, 13),
                              ('cargo', 3650, 'Compra en Café Alameda', 3, 12),
                              ('cargo', 7100, 'Compra en Supermercado El Trigal', 4, 18),
                              ('cargo', 2800, 'Compra en Colaciones La Florida', 5, 14)]
                    if username == 'beneficiario2':
                        values = [('abono', 39000, 'Abono mensual Junaeb', 1, 9),
                                  ('cargo', 6900, 'Compra en Panadería San Gabriel', 4, 15)]
                    for kind, amount, desc, day, hour in values:
                        Movement.objects.create(account=account, kind=kind, amount=amount, description=desc,
                            occurred_at=datetime(month.year, month.month, day, hour, tzinfo=ZoneInfo('America/Santiago')))
        for code, label in [('balance', 'Saldo'), ('movements', 'Movimientos')]:
            ServiceState.objects.get_or_create(code=code, defaults={'label': label, 'available': True})
        # Comercios inventados con nombres y direcciones verosímiles; no corresponden a locales adheridos reales.
        merchants = DEMO_MERCHANTS
        for code, name, category, commune, address, description in merchants:
            Merchant.objects.get_or_create(code=code, defaults={
                'name': name, 'category': category, 'commune': commune,
                'address': address, 'description': description, 'active': True})
        self.stdout.write(self.style.SUCCESS(f'Demostración preparada. Cuentas nuevas: {created_count}. No se modificaron cuentas existentes.'))
