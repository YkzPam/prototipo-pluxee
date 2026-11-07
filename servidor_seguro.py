"""Servidor HTTPS para el prototipo en este equipo."""
import os
import ssl

from cheroot.ssl.builtin import BuiltinSSLAdapter
from cheroot.wsgi import Server

from config.runtime import RUNTIME_DIR
from config.tls_local import CERTIFICATE, PRIVATE_KEY, prepare_certificate
from config.vault import load_vault


def main():
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.production'
    from config.wsgi import application

    vault = load_vault()
    prepare_certificate(vault)
    port = int(os.environ.get('PLUXEE_HTTPS_PORT', '8443'))
    server = Server(('127.0.0.1', port), application, numthreads=12)
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
        server.serve()
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()


if __name__ == '__main__':
    main()
