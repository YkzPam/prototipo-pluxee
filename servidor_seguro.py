"""Servidor HTTPS para el prototipo en este equipo."""
import os
import ssl
import sys
import time

from cheroot.ssl.builtin import BuiltinSSLAdapter
from cheroot.wsgi import Server

from config.runtime import RUNTIME_DIR
from config.tls_local import CERTIFICATE, PRIVATE_KEY, prepare_certificate
from config.vault import load_vault

CERTIFICATE_HINT = (
    '{hora}  AVISO  El navegador rechazó el certificado local ({veces} intento(s) en el último minuto).\n'
    '              Instalar .runtime\\security\\web_tls\\Pluxee_Prototipo_Local.crt en «Entidades de\n'
    '              certificación raíz de confianza» (docs/GUIA_PRESENTACION.md, paso 3) y reabrir el navegador.\n'
)


class LocalServer(Server):
    """Agrupa los rechazos del certificado en un aviso por minuto en vez de una línea por conexión."""
    _rejected = 0
    _last_hint = 0.0

    def error_log(self, msg='', level=20, traceback=False):
        if 'during handshake' in str(msg) and ('CERTIFICATE_UNKNOWN' in str(msg) or 'UNKNOWN_CA' in str(msg)):
            self._rejected += 1
            now = time.monotonic()
            if now - self._last_hint >= 60:
                sys.stderr.write(CERTIFICATE_HINT.format(hora=time.strftime('%H:%M:%S'), veces=self._rejected))
                sys.stderr.flush()
                self._last_hint, self._rejected = now, 0
            return
        super().error_log(msg, level, traceback)


def main():
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.production'
    from config.wsgi import application

    vault = load_vault()
    prepare_certificate(vault)
    port = int(os.environ.get('PLUXEE_HTTPS_PORT', '8443'))
    server = LocalServer(('127.0.0.1', port), application, numthreads=12)
    server.ssl_adapter = BuiltinSSLAdapter(
        str(CERTIFICATE), str(PRIVATE_KEY), private_key_password=vault['TLS_KEY_PASSWORD'])
    server.ssl_adapter.context.minimum_version = ssl.TLSVersion.TLSv1_2
    del vault
    try:
        server.prepare()
        if port == 8443:
            # Solo se registra el proceso después de que pudo abrir el puerto.
            (RUNTIME_DIR / 'https.pid').write_text(f'{os.getpid()}\n', encoding='utf-8')
        print(f'Prototipo académico Pluxee Chile: https://127.0.0.1:{port}/', flush=True)
        print('Registro de páginas atendidas (hora, método, ruta, estado, tiempo, perfil):\n', flush=True)
        server.serve()
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()


if __name__ == '__main__':
    main()
