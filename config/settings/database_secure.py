"""Conexiones MySQL de la demostración local y del aprovisionamiento."""
import re
from config.runtime import RUNTIME_DIR


MYSQL_CA = RUNTIME_DIR / 'mysql_tls' / 'ca.pem'
MYSQL_HOST = '127.0.0.1'
MYSQL_DATABASE = 'pluxee_demo'
APP_USER = 'pluxee_app'
READER_USER = 'pluxee_consulta'


def mysql_parameters(vault):
    host = vault.get('MYSQL_HOST', MYSQL_HOST)
    database = vault.get('MYSQL_DATABASE', MYSQL_DATABASE)
    port = int(vault.get('MYSQL_PORT', 3307))
    if host != MYSQL_HOST or not 1024 <= port <= 65535:
        raise ValueError('La demostración MySQL requiere una dirección local y un puerto válido.')
    if not isinstance(database, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', database):
        raise ValueError('El nombre de la base local MySQL no es válido.')
    return host, port, database


def mysql_tls_options():
    if not MYSQL_CA.is_file():
        raise RuntimeError('No se encuentra la autoridad TLS local de MySQL. Ejecute la preparación de la base.')
    return {'ssl_mode': 'VERIFY_IDENTITY', 'ssl': {'ca': str(MYSQL_CA)}}


def build_databases(vault, *, provisioner=False):
    host, port, database = mysql_parameters(vault)

    def connection(user, key):
        if not vault.get(key):
            raise RuntimeError('Faltan credenciales en la bóveda local de MySQL.')
        return {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': database,
            'USER': user,
            'PASSWORD': vault[key],
            'HOST': host,
            'PORT': port,
            'OPTIONS': {
                'charset': 'utf8mb4',
                'connect_timeout': 5,
                'init_command': "SET SESSION sql_mode='STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION'",
                **mysql_tls_options(),
            },
        }

    if provisioner:
        return {'default': connection('root', 'MYSQL_ROOT_PASSWORD')}
    return {
        'default': connection(APP_USER, 'MYSQL_APP_PASSWORD'),
        'consulta': {
            **connection(READER_USER, 'MYSQL_READER_PASSWORD'),
            'TEST': {'MIRROR': 'default'},
        },
    }
