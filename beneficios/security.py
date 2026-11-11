from datetime import timedelta
from functools import wraps
from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.db import OperationalError, connection, transaction
from django.shortcuts import render
from django.utils import timezone
from django.utils.crypto import salted_hmac
from . import parameters
from .events import record
from .models import LoginThrottle
from .responses import RejectedResponseCreator


def throttle_keys(request, username):
    # No confiar en X-Forwarded-For enviado por el cliente.
    attempts = parameters.current().login_max_attempts
    return [(salted_hmac('login-account', username.casefold()).hexdigest(), attempts),
            (salted_hmac('login-ip', request.META.get('REMOTE_ADDR', '')).hexdigest(), attempts * 6)]


def login_blocked(request, username):
    now = timezone.now()
    return any(LoginThrottle.objects.filter(key=key, blocked_until__gt=now).exists()
               for key, _ in throttle_keys(request, username))


def login_failed(request, username):
    _count_attempts(throttle_keys(request, username))


def allow_registration_attempt(request):
    key = salted_hmac('beneficiary-registration', request.META.get('REMOTE_ADDR', '')).hexdigest()
    return _count_attempts([(key, parameters.current().login_max_attempts * 4)])


def _count_attempts(keys):
    for attempt in range(3):
        try:
            return _store_attempts(keys)
        except OperationalError as error:
            # InnoDB puede revertir la transacción si varios intentos crean el mismo contador.
            if attempt == 2 or connection.vendor != 'mysql' or error.args[:1] != (1213,):
                raise


@transaction.atomic
def _store_attempts(keys):
    now = timezone.now()
    allowed = True
    for key, threshold in keys:
        entry, _ = LoginThrottle.objects.select_for_update().get_or_create(
            key=key, defaults={'window_started': now}
        )
        if not entry.blocked_until or entry.blocked_until <= now:
            if (now - entry.window_started).total_seconds() > settings.LOGIN_WINDOW_SECONDS:
                entry.failures = 0
                entry.window_started = now
            entry.failures += 1
            if entry.failures >= threshold:
                entry.blocked_until = now + timedelta(seconds=settings.LOGIN_LOCK_SECONDS)
            entry.save()
        else:
            allowed = False
    return allowed


def clear_login_failures(request, username):
    # Un ingreso correcto no borra el contador general de IP.
    LoginThrottle.objects.filter(key=throttle_keys(request, username)[0][0]).delete()


def protected(*, api=False, administrator=False):
    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                if api:
                    return RejectedResponseCreator().create_response(
                        request, 'La sesión finalizó o no se ha iniciado. Se debe ingresar nuevamente.',
                        status='expired', http_status=401)
                return redirect_to_login(request.get_full_path())
            if administrator and not request.user.is_staff:
                record(request, 'access', 'denied', 'Intento de acceder al seguimiento sin permiso administrativo.')
                if api:
                    return RejectedResponseCreator().create_response(request)
                return render(request, 'error.html', {'title': 'Acceso restringido', 'status': 403,
                    'message': 'Esta función está disponible únicamente para el administrador autorizado.'}, status=403)
            return view(request, *args, **kwargs)
        return wrapped
    return decorate
