"""Adapter entre servicios de consulta y persistencia académica; operaciones de solo lectura."""
from abc import ABC, abstractmethod
from django.db.models import Sum
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
    @staticmethod
    def check_service(code):
        if not ServiceState.objects.filter(code=code, available=True).exists():
            raise SourceUnavailable

    def balance(self, account):
        self.check_service('balance')
        totals = {row['kind']: row['total'] for row in account.movements.values('kind').annotate(total=Sum('amount'))}
        credited = totals.get(Movement.Kind.CREDIT, 0)
        spent = totals.get(Movement.Kind.DEBIT, 0)
        return {'balance': credited - spent, 'credited': credited, 'spent': spent, 'currency': 'CLP'}

    def movements(self, account, filters):
        self.check_service('movements')
        query = account.movements.all()
        if filters.get('desde'):
            query = query.filter(occurred_at__date__gte=filters['desde'])
        if filters.get('hasta'):
            query = query.filter(occurred_at__date__lte=filters['hasta'])
        if filters.get('tipo') in (Movement.Kind.CREDIT, Movement.Kind.DEBIT):
            query = query.filter(kind=filters['tipo'])
        return query
