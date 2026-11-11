"""Adapter entre servicios de consulta y persistencia académica; operaciones de solo lectura."""
from abc import ABC, abstractmethod
from calendar import monthrange
from datetime import datetime

from django.utils import timezone
from django.utils.formats import date_format

from .database_access import read_alias
from .models import Movement, ServiceState


class SourceUnavailable(Exception):
    def __init__(self, interruption_id=None):
        super().__init__()
        self.interruption_id = interruption_id


class IBenefitServiceAdapter(ABC):
    @abstractmethod
    def balance(self, account):
        raise NotImplementedError

    @abstractmethod
    def movements(self, account, filters):
        raise NotImplementedError


class MockDataServiceAdapter(IBenefitServiceAdapter):
    def __init__(self, *, use_primary=False):
        self.database = 'default' if use_primary else read_alias()

    @staticmethod
    def check_service(code, *, database=None):
        state = (ServiceState.objects.using(database or read_alias()).filter(code=code)
                 .values_list('available', 'active_interruption_id').first())
        if state is None:
            raise SourceUnavailable
        available, interruption_id = state
        if not available:
            raise SourceUnavailable(interruption_id)

    def balance(self, account):
        self.check_service('balance', database=self.database)
        rows = (Movement.objects.using(self.database).filter(account_id=account.pk)
                .order_by().values_list('kind', 'amount'))
        credited, spent = self._totals(rows)
        return {'balance': credited - spent, 'credited': credited, 'spent': spent, 'currency': 'CLP'}

    @staticmethod
    def _totals(rows):
        totals = {Movement.Kind.CREDIT: 0, Movement.Kind.DEBIT: 0}
        for kind, amount in rows.iterator():
            totals[kind] = totals.get(kind, 0) + amount
        return totals[Movement.Kind.CREDIT], totals[Movement.Kind.DEBIT]

    @staticmethod
    def summary_periods():
        now = timezone.localtime()
        month_index = now.year * 12 + now.month - 1
        periods = []
        for offset in range(6):
            year, month = divmod(month_index - offset, 12)
            start = datetime(year, month + 1, 1, tzinfo=now.tzinfo)
            periods.append({'value': start.strftime('%Y-%m'), 'label': date_format(start, 'F Y')})
        return periods

    def monthly_summary(self, account, month=None, *, periods=None):
        now = timezone.localtime()
        zone = now.tzinfo
        periods = periods if periods is not None else self.summary_periods()
        selected = month or periods[0]['value']
        if selected not in {period['value'] for period in periods}:
            raise ValueError('El periodo solicitado no está disponible.')
        year, month_number = map(int, selected.split('-'))
        start = datetime(year, month_number, 1, tzinfo=zone)
        end = datetime(year + (month_number == 12), month_number % 12 + 1, 1, tzinfo=zone)
        query = Movement.objects.using(self.database).filter(
            account_id=account.pk, occurred_at__gte=start, occurred_at__lt=end,
        )
        days = monthrange(year, month_number)[1]
        weekly = [
            {'from_date': start.replace(day=day).date().isoformat(),
             'to_date': start.replace(day=min(day + 6, days)).date().isoformat(),
             'label': f'{day}–{min(day + 6, days)}', 'amount': 0}
            for day in range(1, days + 1, 7)
        ]
        credited, spent = 0, 0
        for kind, amount, occurred_at in query.order_by().values_list('kind', 'amount', 'occurred_at').iterator():
            if kind == Movement.Kind.CREDIT:
                credited += amount
            elif kind == Movement.Kind.DEBIT:
                spent += amount
                weekly[(timezone.localtime(occurred_at).day - 1) // 7]['amount'] += amount
        latest = query.filter(kind=Movement.Kind.DEBIT).values_list('description', 'amount', 'occurred_at').first()
        purchase = None
        if latest:
            description, amount, occurred_at = latest
            purchase = {'description': description, 'amount': amount,
                        'date': timezone.localtime(occurred_at).isoformat()}
        return {'period': date_format(start, 'F Y'), 'month': selected, 'periods': periods,
                'credited': credited, 'spent': spent, 'latest_purchase': purchase, 'weekly': weekly}

    def movements(self, account, filters):
        self.check_service('movements', database=self.database)
        query = Movement.objects.using(self.database).filter(account_id=account.pk)
        if filters.get('desde'):
            query = query.filter(occurred_at__date__gte=filters['desde'])
        if filters.get('hasta'):
            query = query.filter(occurred_at__date__lte=filters['hasta'])
        if filters.get('tipo') in (Movement.Kind.CREDIT, Movement.Kind.DEBIT):
            query = query.filter(kind=filters['tipo'])
        return query
