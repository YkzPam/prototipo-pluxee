"""Prepara MySQL, conserva la demostración anterior e inicia HTTPS."""
from hashlib import sha256
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.tls_local import prepare_certificate
from config.runtime import RUNTIME_DIR
from config.vault import (SECURITY_DIR, prepare_application_secrets, protect_bytes,
                          unprotect_bytes)

PROVISION = '--settings=config.settings.provisioning'
LEGACY = RUNTIME_DIR / 'development.sqlite3'
BACKUP = SECURITY_DIR / 'demostracion_sqlite_anterior.dpapi'


def run(*args):
    subprocess.run([sys.executable, *args], cwd=ROOT, check=True)


def migrate_legacy():
    if not LEGACY.is_file():
        return
    with tempfile.TemporaryDirectory(dir=SECURITY_DIR) as temp:
        snapshot = Path(temp) / 'respaldo.sqlite3'
        with (closing(sqlite3.connect(LEGACY.as_uri() + '?mode=ro', uri=True)) as src,
              closing(sqlite3.connect(snapshot)) as dst):
            src.backup(dst)
            if dst.execute('PRAGMA quick_check').fetchone() != ('ok',):
                raise RuntimeError('La copia SQLite no superó la comprobación de integridad.')
        raw = snapshot.read_bytes()
        if BACKUP.is_file():
            if sha256(unprotect_bytes(BACKUP.read_bytes())).digest() != sha256(raw).digest():
                raise RuntimeError('La base anterior cambió después del respaldo. Revise ambas copias.')
        else:
            secured = protect_bytes(raw)
            if unprotect_bytes(secured) != raw:
                raise RuntimeError('No se pudo comprobar el respaldo protegido.')
            BACKUP.write_bytes(secured)
        run('manage.py', 'migrar_demo_legacy', '--origen', str(snapshot), PROVISION)


def prepare():
    vault = prepare_application_secrets()
    prepare_certificate(vault)
    run('scripts/mysql_local.py', 'preparar')
    run('manage.py', 'migrate', '--noinput', PROVISION)

    # El proceso normal del servidor no recibe credenciales de aprovisionamiento.
    import os
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.provisioning'
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.db import connections

    if not get_user_model().objects.exists():
        migrate_legacy()
        if not get_user_model().objects.exists():
            run('manage.py', 'preparar_demo', PROVISION)
    connections.close_all()
    run('scripts/mysql_local.py', 'permisos')
    run('manage.py', 'collectstatic', '--noinput', '--verbosity=0', PROVISION)


if __name__ == '__main__':
    prepare()
    if sys.argv[1:] != ['--solo-preparar']:
        run('-X', 'utf8', str(ROOT / 'servidor_seguro.py'))
