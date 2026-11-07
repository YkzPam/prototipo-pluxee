"""Verifica el servidor HTTPS local con una cuenta sintética de uso temporal."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from http.cookiejar import CookieJar
from http.cookies import SimpleCookie
import json
import os
from pathlib import Path
import re
import secrets
import socket
import ssl
import sys
from uuid import uuid4
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, HTTPCookieProcessor, ProxyHandler, Request, build_opener


ROOT = Path(__file__).resolve().parents[1]
HOST = '127.0.0.1'
TIMEOUT = 10


class VerificationError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise VerificationError(message)


class KeepRedirects(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Browser:
    def __init__(self, origin, context, csrf_cookie, session_cookie):
        self.origin = origin
        self.csrf_cookie = csrf_cookie
        self.session_cookie = session_cookie
        self.cookies = CookieJar()
        self.session_keys = set()
        self.opener = build_opener(
            ProxyHandler({}), HTTPSHandler(context=context), HTTPCookieProcessor(self.cookies), KeepRedirects(),
        )

    def cookie(self, name):
        return next((cookie for cookie in self.cookies if cookie.name == name), None)

    def request(self, path, *, status=200, data=None, csrf=True):
        headers = {'Origin': self.origin}
        if data is not None and csrf:
            cookie = self.cookie(self.csrf_cookie)
            require(cookie is not None, 'No se recibió la cookie necesaria para enviar el formulario.')
            headers['X-CSRFToken'] = cookie.value
        body = None if data is None else urlencode(data).encode('utf-8')
        request = Request(self.origin + path, data=body, headers=headers)
        try:
            response = self.opener.open(request, timeout=TIMEOUT)
        except HTTPError as error:
            response = error
        with response:
            cookie = self.cookie(self.session_cookie)
            if cookie is not None:
                self.session_keys.add(cookie.value)
            require(response.code == status, f'{urlsplit(path).path} devolvió HTTP {response.code}; se esperaba {status}.')
            return response.headers, response.read()


def verify_cookie(headers, name):
    cookies = SimpleCookie()
    for header in headers.get_all('Set-Cookie', []):
        cookies.load(header)
    cookie = cookies.get(name)
    require(cookie is not None, f'No se recibió la cookie {name}.')
    require(cookie['secure'] and cookie['httponly'] and cookie['samesite'].lower() == 'lax',
            f'La cookie {name} debe declarar Secure, HttpOnly y SameSite=Lax.')


@contextmanager
def temporary_account(browser):
    from django.contrib.auth import get_user_model
    from django.contrib.auth.hashers import make_password
    from django.contrib.sessions.models import Session
    from django.db import connection, transaction
    from beneficios.models import BenefitAccount, DemoCard, Movement, Payment
    from config.vault import load_vault
    from scripts.mysql_local import assert_instance

    with connection.cursor() as cursor:
        assert_instance(cursor, load_vault())
    username = f'verificacion.https.{secrets.token_hex(10)}'
    password = f'Inicio!9{secrets.token_urlsafe(24)}'
    with transaction.atomic():
        user = get_user_model().objects.create_user(
            username=username, password=password, must_change_password=True,
        )
        account = BenefitAccount.objects.create(user=user, number_suffix='9201')
        DemoCard.objects.create(account=account, pin_hash=make_password('4826'))
        Movement.objects.bulk_create([
            Movement(account=account, kind='abono', amount=12000, description='Abono de verificación',
                     occurred_at=datetime(2026, 11, 1, 14, tzinfo=timezone.utc)),
            Movement(account=account, kind='cargo', amount=500, description='Cargo del día anterior en Chile',
                     occurred_at=datetime(2026, 11, 1, 2, 30, tzinfo=timezone.utc)),
            Movement(account=account, kind='cargo', amount=2000, description='Cargo de verificación',
                     occurred_at=datetime(2026, 11, 1, 15, tzinfo=timezone.utc)),
        ])
    try:
        yield user, password, account
    finally:
        with transaction.atomic():
            Session.objects.filter(session_key__in=browser.session_keys).delete()
            Payment.objects.filter(account=account).delete()
            Movement.objects.filter(account=account).delete()
            DemoCard.objects.filter(account=account).delete()
            account.delete()
            # Los eventos mantienen el registro de la prueba y su actor queda nulo.
            user.delete()


def verify_application(browser, context, csrf_cookie, session_cookie):
    from django.urls import reverse
    from beneficios.models import Merchant, Payment

    login_url = reverse('ingresar')
    change_url = reverse('cambiar_clave')
    tracking_url = reverse('seguimiento')
    home_url = reverse('inicio')
    headers, _ = browser.request(login_url)
    hsts = re.search(r'(?:^|;\s*)max-age=(\d+)', headers.get('Strict-Transport-Security', ''), re.I)
    require(hsts and int(hsts[1]) > 0, 'La respuesta HTTPS no contiene una vigencia HSTS positiva.')
    verify_cookie(headers, csrf_cookie)

    with temporary_account(browser) as (user, password, account):
        balance_url = reverse('api_saldo', args=[account.pk])
        browser.request(balance_url, status=401)
        login = {'username': user.username, 'password': password, 'next': tracking_url}
        browser.request(login_url, data=login, csrf=False, status=403)
        headers, _ = browser.request(login_url, data=login, status=302)
        require(headers.get('Location') == change_url, 'La clave temporal no llevó al cambio obligatorio.')
        verify_cookie(headers, session_cookie)
        verify_cookie(headers, csrf_cookie)
        old_session = browser.cookie(session_cookie)
        require(old_session is not None, 'La sesión inicial no quedó disponible para verificar su rotación.')

        headers, _ = browser.request(home_url, status=302)
        require(headers.get('Location') == change_url, 'La portada permitió omitir el cambio de contraseña.')
        _, denied = browser.request(balance_url, status=403)
        require(json.loads(denied).get('status') == 'password_change_required',
                'La API no identificó el bloqueo por contraseña temporal.')
        browser.request(change_url)
        new_password = f'Verificada!8{secrets.token_urlsafe(24)}'
        fields = {'old_password': password, 'new_password1': new_password, 'new_password2': new_password}
        browser.request(change_url, data=fields, csrf=False, status=403)
        headers, _ = browser.request(change_url, data=fields, status=302)
        require(headers.get('Location') == home_url, 'El cambio de contraseña no habilitó el acceso esperado.')
        verify_cookie(headers, session_cookie)
        new_session = browser.cookie(session_cookie)
        require(new_session is not None and new_session.value != old_session.value,
                'El cambio no renovó el identificador de sesión.')

        replay = Browser(browser.origin, context, csrf_cookie, session_cookie)
        replay.cookies.set_cookie(old_session)
        replay.request(balance_url, status=401)
        browser.request(home_url)
        browser.request(tracking_url, status=403)
        _, balance = browser.request(balance_url)
        data = json.loads(balance)
        require(data.get('status') == 'updated' and data.get('data', {}).get('balance') == 9500,
                'La consulta del saldo sintético no devolvió 9500 CLP.')

        filters = urlencode({'desde': '2026-11-01', 'hasta': '2026-11-01', 'tipo': 'cargo'})
        path = reverse('api_movimientos', args=[account.pk])
        _, movements = browser.request(f'{path}?{filters}')
        result = json.loads(movements)
        items = result.get('data', {}).get('items', [])
        require(result.get('status') == 'updated' and len(items) == 1
                and items[0]['kind'] == 'cargo' and items[0]['amount'] == 2000,
                'Los filtros de fecha de Chile y tipo de movimiento no devolvieron el cargo esperado.')

        merchant = Merchant.objects.filter(active=True).first()
        require(merchant is not None, 'Falta el catálogo de comercios de prueba.')
        pay_url = reverse('pagar')
        payment = {'merchant': merchant.pk, 'amount': 1000, 'pin': '4826', 'idempotency_key': str(uuid4())}
        payment_headers, _ = browser.request(pay_url, data=payment, status=302)
        repeated_headers, _ = browser.request(pay_url, data=payment, status=302)
        receipt = Payment.objects.get(account=account)
        receipt_url = reverse('comprobante', args=[receipt.pk])
        require(receipt.amount == 1000 and receipt.balance_after == 8500
                and payment_headers.get('Location') == repeated_headers.get('Location') == receipt_url,
                'El pago repetido no conservó el mismo comprobante o dejó un saldo incorrecto.')
        browser.request(receipt_url)
        _, updated_balance = browser.request(balance_url)
        require(json.loads(updated_balance).get('data', {}).get('balance') == 8500,
                'La consulta no refleja el saldo posterior al pago.')
        browser.request(reverse('salir'), data={}, status=302)
        browser.request(balance_url, status=401)

    return {
        'hsts_segundos': int(hsts[1]),
        'cookies': 'Secure, HttpOnly, SameSite=Lax',
        'csrf': '403 sin token; login y cambio aceptados con token válido',
        'clave_temporal': 'cambio obligatorio con bloqueo de páginas y API',
        'sesion': 'rotada tras el cambio; cookie anterior y cierre denegados con HTTP 401',
        'seguimiento_desde_beneficiario': 403,
        'saldo_sintetico_clp': 9500,
        'movimientos_filtrados': len(items),
        'pago_clp': 1000,
        'saldo_posterior_clp': 8500,
        'pago_repetido': 'mismo comprobante y un solo cargo',
        'limpieza': 'cuenta y sesiones temporales retiradas; auditoría conservada',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--puerto', type=int, default=8443, help='Puerto local del servidor HTTPS.')
    port = parser.parse_args().puerto
    if not 1 <= port <= 65535:
        parser.error('El puerto debe estar entre 1 y 65535.')

    sys.path.insert(0, str(ROOT))
    from config.tls_local import CERTIFICATE

    try:
        require(CERTIFICATE.is_file(), 'No existe el certificado HTTPS local. Se debe iniciar el prototipo.')
        context = ssl.create_default_context(cafile=str(CERTIFICATE))
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        with socket.create_connection((HOST, port), timeout=TIMEOUT) as raw:
            with context.wrap_socket(raw, server_hostname=HOST) as tls:
                protocol, cipher = tls.version(), tls.cipher()[0]

        os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.provisioning'
        import django
        from django.conf import settings
        django.setup()
        browser = Browser(f'https://{HOST}:{port}', context, settings.CSRF_COOKIE_NAME, settings.SESSION_COOKIE_NAME)
        result = verify_application(browser, context, settings.CSRF_COOKIE_NAME, settings.SESSION_COOKIE_NAME)
    except VerificationError as error:
        parser.exit(1, f'La verificación falló. {error}\n')
    except ssl.SSLCertVerificationError:
        parser.exit(1, 'El certificado presentado no superó la validación TLS para 127.0.0.1.\n')
    except Exception as error:
        parser.exit(1, f'No se pudo completar la verificación ({type(error).__name__}).\n')
    print(json.dumps({'tls': protocol, 'cifrado_tls': cipher, **result}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
