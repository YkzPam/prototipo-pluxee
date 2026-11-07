"""Último saldo confirmado para una cuenta en una sesión autenticada."""
from django.core.cache.backends.locmem import LocMemCache
from django.utils.crypto import salted_hmac


# La copia se guarda solo en la memoria del servidor de demostración.
_snapshots = LocMemCache('pluxee-confirmed-balance', {'OPTIONS': {'MAX_ENTRIES': 300}})


def snapshot_key(request, account):
    session_key = request.session.session_key
    if session_key is None:
        return None
    identifier = f'{session_key}:{request.user.pk}:{account.pk}'
    return salted_hmac('pluxee.confirmed-balance', identifier, algorithm='sha256').hexdigest()


def remember_balance(key, *, balance, updated_at, timeout):
    if key and timeout > 0:
        _snapshots.set(key, {'balance': balance, 'updated_at': updated_at}, timeout=timeout)


def last_confirmed_balance(key):
    snapshot = _snapshots.get(key) if key else None
    return {'last_confirmed': snapshot} if snapshot is not None else {}
