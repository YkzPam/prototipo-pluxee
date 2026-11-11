"""Prepara el servidor MySQL portátil de la demostración. Uso: --help."""
import argparse
import hashlib
import ipaddress
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from urllib.request import urlopen
from zipfile import ZipFile


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

import MySQLdb
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from config.settings.database_secure import (
    APP_USER, MYSQL_CA, MYSQL_DATABASE, MYSQL_HOST, READER_USER,
    mysql_parameters, mysql_tls_options,
)
from config.vault import load_vault, restrict_directory, update_vault
from config.runtime import RUNTIME_DIR


VERSION = '8.4.13'
DISTRIBUTION = f'mysql-{VERSION}-winx64'
ZIP_URL = f'https://cdn.mysql.com/Downloads/MySQL-8.4/{DISTRIBUTION}.zip'
# Archivo de Oracle cotejado con su MD5 y firma GPG antes de fijar este SHA-256.
ZIP_SHA256 = 'e9cd98b1d23f122987b1afca26ad942efec5891481103d48ae3cde237fa3ea54'
TZ_ARCHIVE = 'timezone_2026f_posix_sql'
TZ_URL = f'https://downloads.mysql.com/general/{TZ_ARCHIVE}.zip'
TZ_SHA256 = '24c99cb5660e659634311aa015a22e8a7d3f25caec2111b275289b07df7c1948'
RUNTIME = RUNTIME_DIR
BIN_ROOT = RUNTIME / 'mysql_bin'
BASE = BIN_ROOT / DISTRIBUTION
DATA = RUNTIME / 'mysql_data'
TLS = MYSQL_CA.parent
KEY = TLS / 'server-key.pem'
CERT = TLS / 'server-cert.pem'
LOG = DATA / 'mysql-error.log'
PID = DATA / 'mysql.pid'
MYSQLD = BASE / 'bin' / 'mysqld.exe'
MYSQL = BASE / 'bin' / 'mysql.exe'

READER_TABLES = (
    'beneficios_benefitaccount', 'beneficios_movement', 'beneficios_merchant', 'beneficios_servicestate',
)
APP_GRANTS = {
    'auth_group': 'SELECT',
    'auth_group_permissions': 'SELECT',
    'auth_permission': 'SELECT',
    'django_content_type': 'SELECT',
    'django_session': 'SELECT, INSERT, UPDATE, DELETE',
    'identidad_user': (
        'SELECT, INSERT (`username`, `password`, `first_name`, `last_name`, `email`, `date_joined`, '
        '`must_change_password`, `is_active`), UPDATE (`password`, `must_change_password`, `last_login`, '
        '`first_name`, `last_name`, `is_active`, `access_revision`)'
    ),
    'identidad_user_groups': 'SELECT',
    'identidad_user_user_permissions': 'SELECT',
    'beneficios_auditevent': 'SELECT, INSERT',
    'beneficios_notification': 'SELECT, INSERT, UPDATE (`read_at`)',
    'beneficios_benefitaccount': 'SELECT, INSERT',
    'beneficios_democard': 'SELECT, INSERT, UPDATE (`status`, `changed_at`, `dynamic_code_digest`, `dynamic_expires_at`)',
    'beneficios_loginthrottle': 'SELECT, INSERT, UPDATE, DELETE',
    'beneficios_merchant': (
        'SELECT, INSERT (`code`, `name`, `category`, `commune`, `address`, `description`, `active`), '
        'UPDATE (`name`, `category`, `commune`, `address`, `description`, `active`)'
    ),
    'beneficios_merchantfavorite': 'SELECT, INSERT, DELETE',
    'beneficios_movement': 'SELECT, INSERT',
    'beneficios_payment': 'SELECT, INSERT',
    'beneficios_paymentthrottle': 'SELECT, INSERT, UPDATE',
    'beneficios_serviceinterruption': 'SELECT, INSERT, UPDATE (`restored_at`, `verification_note`, `verified_at`, `verified_by_id`)',
    'beneficios_servicestate': 'SELECT, UPDATE (`available`, `changed_at`, `active_interruption_id`)',
    'beneficios_supportreport': 'SELECT, INSERT, UPDATE (`status`, `response`, `updated_at`, `priority`, `assigned_to_id`)',
    'beneficios_supportreportupdate': 'SELECT, INSERT',
    'beneficios_merchantcategory': 'SELECT',
    'beneficios_helptopic': 'SELECT',
    'beneficios_systemparameters': (
        'SELECT, INSERT, UPDATE (`registration_initial_credit`, `login_max_attempts`, `session_idle_minutes`, '
        '`payment_max_amount`, `updated_at`, `updated_by_id`)'
    ),
}


def download_archive(name, url, sha256):
    downloads = RUNTIME / 'downloads'
    downloads.mkdir(parents=True, exist_ok=True)
    archive_path = downloads / f'{name}.zip'
    manual = (f'Se puede descargar {name}.zip en un navegador (archivo de versiones de dev.mysql.com) y copiarlo en '
              f'{downloads}; el inicio comprobará su SHA-256 antes de usarlo.')
    if not archive_path.is_file():
        partial = archive_path.with_suffix('.zip.part')
        try:
            with urlopen(url, timeout=30) as response, partial.open('wb') as output:
                shutil.copyfileobj(response, output, 1024 * 1024)
        except OSError as error:  # incluye URLError, HTTPError y tiempos de espera
            partial.unlink(missing_ok=True)
            raise RuntimeError(f'No fue posible descargar {name}.zip ({error}). {manual}') from None
        partial.replace(archive_path)
    with archive_path.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != sha256:
            # Se elimina para que el siguiente intento descargue de nuevo en lugar de fallar siempre.
            archive_path.unlink(missing_ok=True)
            raise RuntimeError(f'La descarga de {name}.zip no coincide con el archivo verificado. {manual}')
    return archive_path


def install_binary():
    if MYSQLD.is_file() and MYSQL.is_file():
        return
    archive_path = download_archive(DISTRIBUTION, ZIP_URL, ZIP_SHA256)
    with ZipFile(archive_path) as archive:
        for member in archive.infolist():
            name = PurePosixPath(member.filename)
            if (not name.parts or name.parts[0] != DISTRIBUTION or name.is_absolute()
                    or '..' in name.parts or ':' in member.filename or '\\' in member.filename):
                raise RuntimeError('El ZIP de MySQL contiene una ruta inesperada.')
        archive.extractall(BIN_ROOT)


def prepare_tls():
    restrict_directory(TLS)
    if all(path.is_file() for path in (MYSQL_CA, CERT, KEY)):
        return
    if any(path.exists() for path in (MYSQL_CA, CERT, KEY)):
        raise RuntimeError('El conjunto TLS de MySQL está incompleto. No se reemplazó ningún certificado.')
    now = datetime.now(timezone.utc)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Pluxee prototipo MySQL CA local')])
    ca_cert = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name)
               .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
               .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=730))
               .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
               .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False),
                              critical=True)
               .sign(ca_key, hashes.SHA256()))
    server_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    server_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, MYSQL_HOST)])
    server_cert = (x509.CertificateBuilder().subject_name(server_name).issuer_name(ca_name)
                   .public_key(server_key.public_key()).serial_number(x509.random_serial_number())
                   .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=730))
                   .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                   .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(MYSQL_HOST))]),
                                  critical=False)
                   .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
                   .sign(ca_key, hashes.SHA256()))
    KEY.write_bytes(server_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                            serialization.NoEncryption()))
    CERT.write_bytes(server_cert.public_bytes(serialization.Encoding.PEM))
    MYSQL_CA.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))


def can_connect(host, port):
    try:
        with socket.create_connection((host, port), timeout=0.3):
            return True
    except OSError:
        return False


def initial_vault():
    current = load_vault()
    proposed = {}
    if 'MYSQL_PORT' not in current:
        port = next((port for port in (3307, 13306) if not can_connect(MYSQL_HOST, port)), None)
        if port is None:
            raise RuntimeError('Los puertos locales 3307 y 13306 están ocupados.')
        proposed['MYSQL_PORT'] = port
    for name in ('MYSQL_ROOT_PASSWORD', 'MYSQL_APP_PASSWORD', 'MYSQL_READER_PASSWORD'):
        if not current.get(name):
            proposed[name] = secrets.token_urlsafe(40)
    if 'MYSQL_DATABASE' not in current:
        proposed['MYSQL_DATABASE'] = MYSQL_DATABASE
    if 'MYSQL_HOST' not in current:
        proposed['MYSQL_HOST'] = MYSQL_HOST
    if proposed:
        update_vault(proposed)
    return load_vault()


def initialize():
    restrict_directory(DATA)
    if (DATA / 'mysql.ibd').is_file():
        return
    if any(DATA.iterdir()):
        raise RuntimeError('El directorio de datos MySQL tiene archivos de una preparación incompleta.')
    result = subprocess.run(
        [str(MYSQLD), '--no-defaults', '--initialize', '--console',
         f'--basedir={BASE}', f'--datadir={DATA}'],
        capture_output=True, text=True, errors='replace', timeout=120, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    # El mensaje del motor incluye la clave temporal; se procesa en memoria y no se imprime.
    captured = result.stdout + result.stderr
    match = re.search(r'A temporary password is generated for root@localhost: (\S+)', captured)
    if result.returncode or match is None:
        code = re.search(r'\[MY-\d+\]', '\n'.join(line for line in captured.splitlines() if '[ERROR]' in line))
        raise RuntimeError(f'No se pudo inicializar MySQL (código {code[0] if code else result.returncode}).')
    update_vault({'MYSQL_BOOTSTRAP_PASSWORD': match[1]})


def connect(vault, user, key, *, select_database=True, tls=True):
    host, port, db = mysql_parameters(vault)
    options = mysql_tls_options() if tls else {'ssl_mode': 'DISABLED'}
    return MySQLdb.connect(host=host, port=port, user=user, password=vault[key],
                          **({'database': db} if select_database else {}),
                          charset='utf8mb4', connect_timeout=3, local_infile=False, **options)


def assert_instance(cursor, vault):
    cursor.execute('SELECT @@datadir, @@port, @@bind_address, @@require_secure_transport')
    datadir, port, bind, secure = cursor.fetchone()
    host, expected_port, _ = mysql_parameters(vault)
    if Path(datadir).resolve() != DATA.resolve() or (int(port), bind, int(secure)) != (expected_port, host, 1):
        raise RuntimeError('La instancia MySQL no coincide con la instancia privada de la demostración.')


def start(vault, *, bootstrap=False):
    host, port, _ = mysql_parameters(vault)
    if can_connect(host, port):
        if bootstrap:
            # Si se reanuda una rotación interrumpida, el cliente comprueba el TLS
            # de esta instancia antes de enviar una credencial.
            return
        with closing(connect(vault, 'root', 'MYSQL_ROOT_PASSWORD', select_database=False)) as conn, conn.cursor() as cur:
            assert_instance(cur, vault)
        return
    if not MYSQLD.is_file() or not (DATA / 'mysql.ibd').is_file() or not MYSQL_CA.is_file():
        raise RuntimeError('La instancia MySQL todavía no está preparada.')
    process = subprocess.Popen(
        [str(MYSQLD), '--no-defaults', f'--basedir={BASE}', f'--datadir={DATA}', f'--pid-file={PID}',
         f'--log-error={LOG}', f'--bind-address={host}', f'--port={port}', '--mysqlx=OFF',
         '--skip-auto-generate-certs', f'--ssl-ca={MYSQL_CA}', f'--ssl-cert={CERT}', f'--ssl-key={KEY}',
         '--require-secure-transport=ON', '--tls-version=TLSv1.2,TLSv1.3', '--general-log=OFF',
         '--local-infile=OFF', '--secure-file-priv=NULL', '--skip-log-bin', '--default-time-zone=+00:00',
         '--innodb-buffer-pool-size=64M', '--max-connections=100'],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError(f'MySQL se cerró al iniciar (código {process.returncode}). Revise el registro local del motor.')
        if can_connect(host, port):
            if not bootstrap:
                with closing(connect(vault, 'root', 'MYSQL_ROOT_PASSWORD', select_database=False)) as conn, conn.cursor() as cur:
                    assert_instance(cur, vault)
            return
        time.sleep(0.2)
    raise RuntimeError('MySQL no quedó listo en el plazo de inicio.')


def rotate_bootstrap(vault):
    host, port, _ = mysql_parameters(vault)
    password = vault['MYSQL_ROOT_PASSWORD']
    if not re.fullmatch(r'[A-Za-z0-9_-]{40,}', password):
        raise RuntimeError('La contraseña de aprovisionamiento no tiene el formato local esperado.')
    try:
        with closing(connect(vault, 'root', 'MYSQL_ROOT_PASSWORD', select_database=False)) as conn, conn.cursor() as cur:
            assert_instance(cur, vault)
    except MySQLdb.OperationalError:
        # Cliente en modo lote; la clave temporal existe solo en el entorno del proceso hijo.
        environment = {name: value for name, value in os.environ.items() if not name.upper().startswith('MYSQL')}
        environment['MYSQL_PWD'] = vault['MYSQL_BOOTSTRAP_PASSWORD']
        result = subprocess.run(
            [str(MYSQL), '--no-defaults', '--no-login-paths', '--batch', '--connect-expired-password',
             '--protocol=TCP', f'--host={host}', f'--port={port}', '--user=root',
             '--ssl-mode=VERIFY_IDENTITY', f'--ssl-ca={MYSQL_CA}'],
            input=f"ALTER USER USER() IDENTIFIED BY '{password}';\n", text=True,
            capture_output=True, env=environment, timeout=20, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode:
            code = re.search(r'ERROR (\d+)', result.stderr)
            raise RuntimeError(f'No se pudo rotar la clave inicial MySQL (código {code[1] if code else result.returncode}).')
        with closing(connect(vault, 'root', 'MYSQL_ROOT_PASSWORD', select_database=False)) as conn, conn.cursor() as cur:
            assert_instance(cur, vault)
    update_vault({'MYSQL_BOOTSTRAP_PASSWORD': ''})


def fill_time_zones(cursor):
    cursor.execute("SELECT 1 FROM mysql.time_zone_transition t JOIN mysql.time_zone_name n "
                   "ON t.Time_zone_id = n.Time_zone_id WHERE n.Name = 'America/Santiago' LIMIT 1")
    if cursor.fetchone():
        return False
    cursor.execute('USE mysql')
    with ZipFile(download_archive(TZ_ARCHIVE, TZ_URL, TZ_SHA256)) as archive:
        source = archive.read(f'{TZ_ARCHIVE}/timezone_posix.sql').decode('utf-8')
    # El archivo POSIX verificado de Oracle solo altera las tablas horarias de mysql.
    for statement in source.split(';'):
        if statement.strip():
            cursor.execute(statement)
    return True


def check_santiago(cursor):
    cursor.execute("SELECT CONVERT_TZ('2026-11-01 03:00:00', 'UTC', 'America/Santiago'), "
                   "CONVERT_TZ('2026-07-01 03:00:00', 'UTC', 'America/Santiago')")
    summer, winter = map(str, cursor.fetchone())
    if (summer, winter) != ('2026-11-01 00:00:00', '2026-06-30 23:00:00'):
        raise RuntimeError('MySQL no aplica los desfases de verano e invierno de Santiago.')
    return {'noviembre': summer, 'julio': winter}


def prepare():
    install_binary()
    prepare_tls()
    vault = initial_vault()
    initialize()
    vault = load_vault()
    start(vault, bootstrap=bool(vault.get('MYSQL_BOOTSTRAP_PASSWORD')))
    if vault.get('MYSQL_BOOTSTRAP_PASSWORD'):
        rotate_bootstrap(vault)
    host, port, database = mysql_parameters(vault)
    with closing(connect(vault, 'root', 'MYSQL_ROOT_PASSWORD', select_database=False)) as conn, conn.cursor() as cur:
        conn.autocommit(True)
        assert_instance(cur, vault)
        cur.execute("ALTER USER 'root'@'localhost' REQUIRE SSL")
        cur.execute(f'CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci')
        for user, key in ((APP_USER, 'MYSQL_APP_PASSWORD'), (READER_USER, 'MYSQL_READER_PASSWORD')):
            cur.execute(f"CREATE USER IF NOT EXISTS '{user}'@'{host}' IDENTIFIED BY %s REQUIRE SSL", (vault[key],))
        loaded = fill_time_zones(cur)
    if loaded:
        stop(vault)
        start(vault)
    with closing(connect(vault, 'root', 'MYSQL_ROOT_PASSWORD')) as conn, conn.cursor() as cur:
        check_santiago(cur)
    print(f'MySQL {VERSION} listo en {host}:{port}; faltan migraciones y permisos de aplicación si es la primera ejecución.')


def grants(vault):
    host, _, database = mysql_parameters(vault)
    with closing(connect(vault, 'root', 'MYSQL_ROOT_PASSWORD')) as conn, conn.cursor() as cur:
        conn.autocommit(True)
        assert_instance(cur, vault)
        cur.execute('SHOW TABLES')
        tables = {row[0] for row in cur.fetchall()}
        missing = set(APP_GRANTS) - tables
        if missing:
            raise RuntimeError(f'Faltan tablas migradas: {", ".join(sorted(missing))}.')
        for user in (APP_USER, READER_USER):
            cur.execute(f"REVOKE ALL PRIVILEGES, GRANT OPTION FROM '{user}'@'{host}'")
        for table, privileges in APP_GRANTS.items():
            cur.execute(f"GRANT {privileges} ON `{database}`.`{table}` TO '{APP_USER}'@'{host}'")
        for table in READER_TABLES:
            cur.execute(f"GRANT SELECT ON `{database}`.`{table}` TO '{READER_USER}'@'{host}'")
    print('Permisos por tabla aplicados a pluxee_app y pluxee_consulta.')


def rejection(cursor, statement, codes=(1044, 1142, 1143)):
    try:
        cursor.execute(statement)
    except MySQLdb.Error as error:
        if error.args and error.args[0] in codes:
            return error.args[0]
        raise
    raise RuntimeError('El motor permitió una operación que debía denegar.')


def status(cursor, variable):
    cursor.execute('SHOW SESSION STATUS LIKE %s', (variable,))
    return cursor.fetchone()[1]


def verify(vault):
    checks = {}
    with closing(connect(vault, READER_USER, 'MYSQL_READER_PASSWORD')) as conn, conn.cursor() as cur:
        cur.execute('SELECT CURRENT_USER(), VERSION()')
        checks['consulta'], checks['version'] = cur.fetchone()
        checks['tls_consulta'] = {'version': status(cur, 'Ssl_version'), 'cifrado': status(cur, 'Ssl_cipher')}
        for table in READER_TABLES:
            cur.execute(f'SELECT 1 FROM `{table}` LIMIT 1')
        checks['lectura_autorizada'] = READER_TABLES
        checks['lecturas_denegadas'] = {
            table: rejection(cur, f'SELECT 1 FROM `{table}` LIMIT 1')
            for table in ('identidad_user', 'django_session', 'beneficios_auditevent', 'beneficios_payment',
                          'beneficios_supportreport')
        }
        checks['escrituras_denegadas_consulta'] = {
            'UPDATE': rejection(cur, 'UPDATE beneficios_servicestate SET available = 1 WHERE 1 = 0'),
            'INSERT': rejection(cur, 'INSERT INTO beneficios_servicestate (code, label, available, changed_at) '
                                'SELECT code, label, available, changed_at FROM beneficios_servicestate WHERE 1 = 0'),
        }
    with closing(connect(vault, APP_USER, 'MYSQL_APP_PASSWORD')) as conn, conn.cursor() as cur:
        cur.execute('SELECT CURRENT_USER()')
        checks['app'] = cur.fetchone()[0]
        checks['tls_app'] = {'version': status(cur, 'Ssl_version'), 'cifrado': status(cur, 'Ssl_cipher')}
        cur.execute('UPDATE beneficios_servicestate SET available = 1 WHERE 1 = 0')
        checks['actualizacion_autorizada_app_sin_cambiar_filas'] = cur.rowcount == 0
        checks['cambio_privilegios_usuario_denegado_app'] = rejection(
            cur, 'UPDATE identidad_user SET is_staff = 1 WHERE 1 = 0')
        checks['cambio_titular_reporte_denegado_app'] = rejection(
            cur, 'UPDATE beneficios_supportreport SET reporter_id = reporter_id WHERE 1 = 0')
        name = f'chequeo_permiso_{secrets.token_hex(8)}'
        try:
            checks['create_denegado_app'] = rejection(cur, f'CREATE TABLE `{name}` (id INT)')
        except RuntimeError:
            # Solo se retira la tabla aleatoria que creó esta prueba si los permisos fueran erróneos.
            with closing(connect(vault, 'root', 'MYSQL_ROOT_PASSWORD')) as owner, owner.cursor() as owner_cur:
                assert_instance(owner_cur, vault)
                owner_cur.execute(f'DROP TABLE `{name}`')
            raise
        checks['america_santiago'] = check_santiago(cur)
    try:
        with closing(connect(vault, READER_USER, 'MYSQL_READER_PASSWORD', tls=False)):
            raise RuntimeError('MySQL permitió una conexión sin TLS.')
    except MySQLdb.OperationalError as error:
        if not error.args or error.args[0] not in (1045, 3159):
            raise
        checks['sin_tls_denegado'] = error.args[0]
    if not all(checks[key]['cifrado'] for key in ('tls_consulta', 'tls_app')):
        raise RuntimeError('Falta cifrado en una conexión de aplicación.')
    print(json.dumps(checks, ensure_ascii=False, indent=2))


def stop(vault):
    host, port, _ = mysql_parameters(vault)
    if not can_connect(host, port):
        print('La instancia MySQL ya está detenida.')
        return
    with closing(connect(vault, 'root', 'MYSQL_ROOT_PASSWORD', select_database=False)) as conn, conn.cursor() as cur:
        assert_instance(cur, vault)
        cur.execute('SHUTDOWN')
    for _ in range(100):
        if not can_connect(host, port) and not PID.exists():
            print('Instancia MySQL de la demostración detenida.')
            return
        time.sleep(0.2)
    raise RuntimeError('No se confirmó la detención de la instancia MySQL.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('accion', choices=('preparar', 'iniciar', 'permisos', 'verificar', 'detener'))
    action = parser.parse_args().accion
    if os.name != 'nt':
        parser.exit(1, 'Esta preparación portátil está destinada a Windows.\n')
    try:
        if action == 'preparar':
            prepare()
        else:
            vault = load_vault()
            if action == 'iniciar':
                start(vault)
                print('MySQL listo en el puerto local configurado.')
            else:
                {'permisos': grants, 'verificar': verify, 'detener': stop}[action](vault)
    except MySQLdb.Error as error:
        # No imprime mensajes SQL que pudieran incluir información reservada.
        parser.exit(1, f'Error MySQL al {action} (código {error.args[0] if error.args else "desconocido"}).\n')
    except RuntimeError as error:
        parser.exit(1, f'{error}\n')
    except (OSError, KeyError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f'No se pudo {action} MySQL ({type(error).__name__}).\n')


if __name__ == '__main__':
    main()
