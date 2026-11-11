"""Alta de beneficiarios con permisos MySQL limitados por columna."""
from secrets import randbelow

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.db import connection, transaction
from django.utils import timezone

from beneficios.events import log_committed_movement
from beneficios.models import BenefitAccount, DemoCard, Movement
from beneficios.parameters import current as current_parameters


@transaction.atomic
def create_beneficiary(values):
    """Registra usuario, cuenta, tarjeta y abono inicial en una transacción."""
    User = get_user_model()
    user = User(username=values['username'], first_name=values['first_name'], last_name=values['last_name'])
    user.set_password(values['password1'])
    # Se omiten las columnas de rol. MySQL aplica sus valores por defecto y
    # la cuenta de aplicación carece de permiso para escribirlas.
    fields = [User._meta.get_field(name) for name in (
        'username', 'password', 'first_name', 'last_name', 'email', 'date_joined',
        'must_change_password', 'is_active',
    )]
    if connection.vendor == 'mysql':
        quote = connection.ops.quote_name
        table = quote(User._meta.db_table)
        columns = ', '.join(quote(field.column) for field in fields)
        placeholders = ', '.join(['%s'] * len(fields))
        params = [field.get_db_prep_save(field.value_from_object(user), connection) for field in fields]
        with connection.cursor() as cursor:
            cursor.execute(f'INSERT INTO {table} ({columns}) VALUES ({placeholders})', params)
            user_id = cursor.lastrowid
    else:
        user.save(force_insert=True)
        user_id = user.pk
    account = BenefitAccount.objects.create(user_id=user_id, number_suffix=f'{randbelow(10000):04d}')
    DemoCard.objects.create(account=account, pin_hash=make_password(values['pin']))
    credit = current_parameters().registration_initial_credit
    if credit:
        movement = Movement.objects.create(
            account=account, kind=Movement.Kind.CREDIT, amount=credit,
            description='Abono inicial', occurred_at=timezone.now(),
        )
        log_committed_movement(movement)
    return user_id
