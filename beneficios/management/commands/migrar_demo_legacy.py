"""Traslada datos sintéticos desde el esquema SQLite anterior."""

import sqlite3
from contextlib import closing
from datetime import timezone
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, identify_hasher, is_password_usable, make_password
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import no_style
from django.db import DatabaseError, connection, models, transaction

from beneficios.demo_credentials import ADMIN_PASSWORD, BENEFICIARY_PASSWORD
from beneficios.models import (
    AuditEvent,
    BenefitAccount,
    DemoCard,
    LoginThrottle,
    Merchant,
    MerchantFavorite,
    Movement,
    Payment,
    PaymentThrottle,
    ServiceState,
)


def checked_hash(value):
    if not isinstance(value, str) or not value:
        raise CommandError('El origen contiene un formato de credencial incompatible.')
    if is_password_usable(value):
        try:
            identify_hasher(value)
        except ValueError:
            raise CommandError('El origen contiene un formato de credencial incompatible.') from None


def copy_rows(source, source_table, model, *, user_table=False):
    fields = [field for field in model._meta.local_concrete_fields
              if field.name != 'must_change_password']
    source_columns = {row['name'] for row in source.execute(f'PRAGMA table_info("{source_table}")')}
    if any(field.column not in source_columns for field in fields):
        raise CommandError(f'El esquema SQLite anterior no corresponde a la tabla {source_table}.')

    count = 0
    for row in source.execute(f'SELECT * FROM "{source_table}"'):
        values = {}
        for field in fields:
            value = field.to_python(row[field.column])
            if isinstance(field, models.DateTimeField) and value is not None and value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            values[field.attname] = value
        if user_table:
            checked_hash(values['password'])
            if (values['username'] == 'administrador' and values['is_staff']
                    and check_password(BENEFICIARY_PASSWORD, values['password'])):
                values['password'] = make_password(ADMIN_PASSWORD)
        if model is DemoCard:
            checked_hash(values['pin_hash'])
        # La inserción cruda del ORM conserva fechas automáticas y aplica el cifrado de campos.
        model(**values).save_base(raw=True, force_insert=True, using='default')
        count += 1
    return count


class Command(BaseCommand):
    help = 'Importa una copia SQLite de la demostración anterior en una base ya migrada y vacía.'

    def add_arguments(self, parser):
        parser.add_argument('--origen', type=Path, required=True, help='Ruta a la copia SQLite.')

    def handle(self, *args, **options):
        source_path = options['origen'].resolve()
        if not source_path.is_file():
            raise CommandError('No existe la copia SQLite indicada.')
        if connection.vendor == 'sqlite' and Path(connection.settings_dict['NAME']).resolve() == source_path:
            raise CommandError('El destino y el origen deben ser archivos distintos.')

        user_model = get_user_model()
        if user_model._meta.label_lower != 'identidad.user':
            raise CommandError('El destino requiere el modelo de usuario con cifrado.')
        data_models = (
            user_model, BenefitAccount, Merchant, DemoCard, Movement, Payment,
            MerchantFavorite, ServiceState, AuditEvent,
        )
        excluded_models = (Session, LoginThrottle, PaymentThrottle)

        try:
            with closing(sqlite3.connect(source_path.as_uri() + '?mode=ro', uri=True)) as source:
                source.row_factory = sqlite3.Row
                source.execute('BEGIN')
                if source.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                    raise CommandError('La copia SQLite no supera la revisión de integridad.')
                if source.execute('PRAGMA foreign_key_check').fetchone():
                    raise CommandError('La copia SQLite contiene relaciones sin su registro de origen.')
                for table in ('auth_group', 'auth_user_groups', 'auth_user_user_permissions'):
                    if source.execute(f'SELECT 1 FROM "{table}" LIMIT 1').fetchone():
                        raise CommandError('La copia contiene permisos adicionales que requieren traslado manual.')

                with transaction.atomic(using='default'):
                    if any(model.objects.using('default').exists() for model in (*data_models, *excluded_models)):
                        raise CommandError('El destino debe estar migrado y vacío antes del traslado.')

                    counts = {}
                    for model in data_models:
                        user_table = model is user_model
                        source_table = 'auth_user' if user_table else model._meta.db_table
                        counts[model._meta.label] = copy_rows(source, source_table, model, user_table=user_table)
                    with connection.cursor() as cursor:
                        for statement in connection.ops.sequence_reset_sql(no_style(), data_models):
                            cursor.execute(statement)
        except (sqlite3.Error, DatabaseError, ValidationError, ValueError):
            raise CommandError('El traslado se canceló. Revise el esquema de origen y las migraciones del destino.') from None

        for label, count in counts.items():
            self.stdout.write(f'{label} = {count}')
        self.stdout.write(self.style.SUCCESS(
            'Traslado completado. Las sesiones y los contadores de intentos quedaron fuera.'
        ))
