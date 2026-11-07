"""Bóveda local para el usuario de Windows que ejecuta el prototipo."""
import base64
import csv
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
SECURITY_DIR = ROOT / '.runtime' / 'security'
VAULT = SECURITY_DIR / 'vault.dpapi'


class Blob(ctypes.Structure):
    _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_ubyte))]


def _dpapi(data, *, encrypt):
    if os.name != 'nt':
        raise RuntimeError('La bóveda de la demostración requiere Windows.')
    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source = Blob(len(data), buffer)
    output = Blob()
    api = ctypes.WinDLL('crypt32', use_last_error=True)
    function = api.CryptProtectData if encrypt else api.CryptUnprotectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise ctypes.WinError(ctypes.get_last_error())
    free = ctypes.WinDLL('kernel32').LocalFree
    free.argtypes = [ctypes.c_void_p]
    free.restype = ctypes.c_void_p
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        free(output.pbData)


def protect_bytes(data):
    return _dpapi(data, encrypt=True)


def unprotect_bytes(data):
    return _dpapi(data, encrypt=False)


def restrict_directory(path):
    path = Path(path)
    runtime = ROOT / '.runtime'
    if runtime.resolve() != runtime or runtime not in path.resolve().parents or path.resolve() != path:
        raise ValueError('El directorio de seguridad debe estar dentro del proyecto.')
    path.mkdir(parents=True, exist_ok=True)
    who = subprocess.check_output(['whoami', '/user', '/fo', 'csv', '/nh'], text=True)
    sid = next(csv.reader(who.strip().splitlines()))[1]
    subprocess.run(['icacls', str(path), '/inheritance:r', '/grant:r',
                    f'*{sid}:(OI)(CI)F', '*S-1-5-18:(OI)(CI)F'],
                   check=True, stdout=subprocess.DEVNULL)


def load_vault():
    if not VAULT.is_file():
        return {}
    result = json.loads(unprotect_bytes(VAULT.read_bytes()))
    if not isinstance(result, dict):
        raise ValueError('Contenido inesperado en la bóveda local.')
    return result


def update_vault(updates, *, defaults_only=False):
    import msvcrt

    restrict_directory(SECURITY_DIR)
    with (SECURITY_DIR / 'vault.lock').open('a+b') as lock:
        for attempt in range(100):
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                if attempt == 99:
                    raise
                time.sleep(0.1)
        try:
            existing = load_vault()
            result = {**updates, **existing} if defaults_only else {**existing, **updates}
            blob = protect_bytes(json.dumps(result, ensure_ascii=True).encode('utf-8'))
            with tempfile.NamedTemporaryFile(dir=SECURITY_DIR, delete=False) as temp:
                temp.write(blob)
                temp.flush()
                os.fsync(temp.fileno())
            try:
                os.replace(temp.name, VAULT)
            finally:
                Path(temp.name).unlink(missing_ok=True)
            return result
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def prepare_application_secrets():
    current = load_vault()
    defaults = {
        'DJANGO_SECRET_KEY': secrets.token_urlsafe(64),
        'DATA_ENCRYPTION_KEY': base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('ascii'),
        'TLS_KEY_PASSWORD': secrets.token_urlsafe(32),
    }
    missing = {key: value for key, value in defaults.items() if key not in current}
    return update_vault(missing, defaults_only=True) if missing else current


def require_application_secrets(vault):
    key = base64.urlsafe_b64decode(vault.get('DATA_ENCRYPTION_KEY', ''))
    secret = vault.get('DJANGO_SECRET_KEY', '')
    if len(key) != 32 or len(secret) < 50:
        raise RuntimeError('Falta la configuración protegida. Ejecute iniciar.cmd.')
    return secret, key
