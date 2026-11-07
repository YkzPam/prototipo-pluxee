"""Adapter entre servicios de consulta y persistencia académica; operaciones de solo lectura."""
from abc import ABC, abstractmethod

from .database_access import read_alias
from .models import Movement, ServiceState


class SourceUnavailable(Exception):
    pass


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
        if not ServiceState.objects.using(database or read_alias()).filter(code=code, available=True).exists():
            raise SourceUnavailable

    def balance(self, account):
        self.check_service('balance', database=self.database)
        rows = (Movement.objects.using(self.database).filter(account_id=account.pk)
                .order_by().values_list('kind', 'amount'))
        totals = {Movement.Kind.CREDIT: 0, Movement.Kind.DEBIT: 0}
        for kind, amount in rows.iterator():
            totals[kind] = totals.get(kind, 0) + amount
        credited = totals[Movement.Kind.CREDIT]
        spent = totals[Movement.Kind.DEBIT]
        return {'balance': credited - spent, 'credited': credited, 'spent': spent, 'currency': 'CLP'}

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
