"""Instala un ZIP verificado en la demostración local HTTPS de Windows."""
import argparse
import ctypes
from ctypes import wintypes
from contextlib import ExitStack
from datetime import datetime, timezone
from hashlib import file_digest
from html.parser import HTMLParser
from http.client import HTTPException, HTTPSConnection
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
import socket
import ssl
import stat
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from urllib.parse import urlsplit
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / '.runtime'
DIST = ROOT / 'dist'
PORT = 8443
HOST = '127.0.0.1'
ARCHIVE_ROOT = 'Prototipo_Pluxee_Chile'
SERVER = 'servidor_seguro.py'
PID_FILE = RUNTIME / 'https.pid'


def sha256(path):
    with path.open('rb') as source:
        return file_digest(source, 'sha256').hexdigest()


def stage_release(archive):
    releases = RUNTIME / 'releases'
    releases.mkdir(parents=True, exist_ok=True)
    if releases.resolve() != releases or RUNTIME.resolve() != RUNTIME:
        raise RuntimeError('La ruta de versiones debe pertenecer a este proyecto.')
    with archive.open('rb') as source:
        digest = file_digest(source, 'sha256').hexdigest()
        source.seek(0)
        # Windows limita la longitud de algunas rutas que usa el cargador de Python.
        # La huella completa queda en el registro y la reutilización compara cada archivo.
        release = releases / digest[:20]
        with ZipFile(source) as bundle:
            entries = {}
            seen = set()
            for item in bundle.infolist():
                path = PurePosixPath(item.filename)
                if (not path.parts or path.parts[0] != ARCHIVE_ROOT or len(path.parts) < 2
                        or '\\' in item.filename or ':' in item.filename or '..' in path.parts
                        or any(part.endswith(('.', ' ')) or PureWindowsPath(part).is_reserved()
                               for part in path.parts)
                        or stat.S_ISLNK(item.external_attr >> 16)):
                    raise RuntimeError('El ZIP contiene una ruta de instalación inválida.')
                key = PurePosixPath(*path.parts[1:]).as_posix()
                if key.casefold() in seen:
                    raise RuntimeError('El ZIP contiene una ruta repetida.')
                seen.add(key.casefold())
                if not item.is_dir():
                    entries[key] = item
            required = {SERVER, 'manage.py', 'config/settings/production.py',
                        'scripts/arranque_seguro.py', 'scripts/verificar_https.py'}
            if not required <= entries.keys() or bundle.testzip() is not None:
                raise RuntimeError('El ZIP está incompleto o presenta un error de integridad.')
            if release.exists():
                for name, item in entries.items():
                    target = release / name
                    if target.resolve() != target or not target.is_file():
                        raise RuntimeError('La versión ya extraída fue modificada.')
                    with bundle.open(item) as member:
                        if file_digest(member, 'sha256').hexdigest() != sha256(target):
                            raise RuntimeError('La versión ya extraída fue modificada.')
            else:
                with TemporaryDirectory(prefix='extraccion-', dir=releases) as temp:
                    staging = Path(temp) / 'version'
                    for name, item in entries.items():
                        target = staging / name
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with bundle.open(item) as member, target.open('wb') as output:
                            shutil.copyfileobj(member, output)
                    staging.replace(release)
    return release, digest


def environment(port):
    return {**os.environ, 'PLUXEE_RUNTIME_DIR': str(RUNTIME), 'PLUXEE_HTTPS_PORT': str(port),
            'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'}


def checked(release, *args, port=PORT):
    result = subprocess.run([sys.executable, *args], cwd=release, env=environment(port),
                            text=True, encoding='utf-8', capture_output=True, timeout=180)
    if result.returncode:
        output = (result.stdout + result.stderr).strip()
        raise RuntimeError(f'Falló {args[0]} (código {result.returncode}). {output}')
    return result.stdout


def windows_argv(command):
    shell = ctypes.WinDLL('shell32', use_last_error=True)
    shell.CommandLineToArgvW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
    shell.CommandLineToArgvW.restype = ctypes.POINTER(wintypes.LPWSTR)
    free = ctypes.WinDLL('kernel32', use_last_error=True).LocalFree
    free.argtypes = [ctypes.c_void_p]
    free.restype = ctypes.c_void_p
    count = ctypes.c_int()
    argv = shell.CommandLineToArgvW(command, ctypes.byref(count))
    if not argv:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return [argv[index] for index in range(count.value)]
    finally:
        free(argv)


def process_identity():
    # Consultar el propietario real del puerto, no confiar solo en un PID archivado.
    # Una conexión propia permite identificar el servidor si la escucha no aparece.
    with ExitStack() as stack:
        try:
            probe = stack.enter_context(socket.create_connection((HOST, PORT), timeout=3))
            peer_port = probe.getsockname()[1]
        except ConnectionRefusedError:
            peer_port = 0
        if peer_port:
            certificate = RUNTIME / 'security' / 'web_tls' / 'Pluxee_Prototipo_Local.crt'
            context = ssl.create_default_context(cafile=str(certificate))
            stack.enter_context(context.wrap_socket(probe, server_hostname=HOST))
        command = f"""
$ErrorActionPreference = 'Stop'
$listeners = @(Get-NetTCPConnection -State Listen -LocalPort {PORT} -ErrorAction SilentlyContinue)
if ($listeners.Count -gt 1 -or ($listeners.Count -eq 1 -and $listeners[0].LocalAddress -ne '{HOST}')) {{
    throw 'El puerto tiene otro propietario'
}}
$listenerId = if ($listeners.Count -eq 1) {{ $listeners[0].OwningProcess }} else {{ 0 }}
if ({peer_port} -ne 0) {{
    $connection = @()
    for ($attempt = 0; $attempt -lt 3 -and $connection.Count -eq 0; $attempt++) {{
        $connection = @(Get-NetTCPConnection -LocalPort {PORT} -RemotePort {peer_port} -State Established -ErrorAction SilentlyContinue)
    }}
    if ($connection.Count -ne 1 -or $connection[0].LocalAddress -ne '{HOST}' -or
        ($listenerId -ne 0 -and $listenerId -ne $connection[0].OwningProcess)) {{
        throw 'No se pudo confirmar quién atendió la conexión de prueba'
    }}
    $listenerId = $connection[0].OwningProcess
}}
if ($listenerId -eq 0) {{ 'null'; exit }}
$child = Get-CimInstance Win32_Process -Filter "ProcessId = $listenerId"
$parentId = $child.ParentProcessId
$parent = Get-CimInstance Win32_Process -Filter "ProcessId = $parentId"
@{{pid=$child.ProcessId; exe=$child.ExecutablePath; cmd=$child.CommandLine;
   parent=$parent.ProcessId; parentExe=$parent.ExecutablePath; parentCmd=$parent.CommandLine}} | ConvertTo-Json -Compress
"""
        result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                                 "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8\n" + command],
                                capture_output=True, encoding='utf-8', timeout=12)
    if result.returncode or not result.stdout.strip():
        raise RuntimeError('No se pudo identificar de forma segura el proceso del puerto de demostración.')
    return json.loads(result.stdout)


def active_process(expected=None):
    for attempt in range(3):
        try:
            owner = process_identity()
            break
        except (RuntimeError, TimeoutError, subprocess.TimeoutExpired):
            if attempt == 2:
                raise
    if owner is None:
        return None
    if expected is None:
        try:
            expected = int(PID_FILE.read_text(encoding='utf-8').strip())
        except (OSError, ValueError):
            raise RuntimeError('El servidor activo no tiene un PID de este proyecto.') from None
    python = Path(sys.executable).resolve()
    listener = Path(owner['exe'] or '').resolve()
    base_python = Path(sys._base_executable).resolve()
    parent = owner['parent']
    if (expected == parent and Path(owner['parentExe'] or '').resolve() == python
            and listener in {python, base_python}):
        argv = windows_argv(owner['parentCmd'])
        listener_argv = windows_argv(owner['cmd'])
        if argv[1:] != listener_argv[1:]:
            raise RuntimeError('El proceso hijo no corresponde a este servidor.')
    elif expected == owner['pid'] and listener in {python, base_python}:
        argv = windows_argv(owner['cmd'])
    else:
        raise RuntimeError('El puerto de demostración pertenece a otro proceso.')
    if len(argv) != 4 or argv[1:3] != ['-X', 'utf8']:
        raise RuntimeError('El servidor activo se inició con una orden distinta a la del proyecto.')
    script = Path(argv[-1])
    if script == Path(SERVER):
        script = ROOT / script
    if not (script.is_absolute() and script.resolve() == script and script.name == SERVER
            and script.is_file() and (script.parent == ROOT or script.parent.parent == RUNTIME / 'releases')):
        raise RuntimeError('La ruta del servidor activo está fuera del proyecto.')
    return expected, script


def stop_tree(pid):
    subprocess.run(['taskkill.exe', '/PID', str(pid), '/T', '/F'], check=True, timeout=12,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def launch(script, port, label):
    with (RUNTIME / f'{label}.log').open('ab') as output:
        return subprocess.Popen([sys.executable, '-X', 'utf8', str(script)], cwd=script.parent,
                                env=environment(port), stdout=output, stderr=subprocess.STDOUT,
                                creationflags=subprocess.CREATE_NO_WINDOW)


class LoginAssets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.assets = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        path = attrs.get('src') if tag == 'script' else (
            attrs.get('href') if tag == 'link' and attrs.get('rel') == 'stylesheet' else None)
        if path and path.startswith('/static/') and urlsplit(path).netloc == '':
            self.assets.add(path)


def health(port, *, check_assets=False):
    certificate = RUNTIME / 'security' / 'web_tls' / 'Pluxee_Prototipo_Local.crt'
    context = ssl.create_default_context(cafile=str(certificate))
    paths = ['/ingresar/']
    assets = set()
    while paths:
        path = paths.pop()
        conn = HTTPSConnection(HOST, port, timeout=3, context=context)
        try:
            conn.request('GET', path)
            response = conn.getresponse()
            content = response.read()
            if response.status != 200 or not content:
                raise RuntimeError(f'Respuesta inesperada en {path}.')
            if path == '/ingresar/':
                # Marca del título del sitio (base.html); debe coincidir si se cambia el nombre del portal.
                if b'Portal de beneficios' not in content or not response.headers.get('Strict-Transport-Security'):
                    raise RuntimeError('La respuesta no corresponde al prototipo HTTPS.')
                if check_assets:
                    parser = LoginAssets()
                    parser.feed(content.decode('utf-8'))
                    assets = parser.assets
                    if not assets:
                        raise RuntimeError('No se identificaron recursos del formulario de ingreso.')
                    paths.extend(sorted(assets))
        finally:
            conn.close()
    return sorted(assets)


def ready(process, port, *, check_assets=False):
    deadline = time.monotonic() + 15
    while process.poll() is None:
        try:
            return health(port, check_assets=check_assets)
        except (OSError, HTTPException, RuntimeError) as error:
            if time.monotonic() >= deadline:
                raise RuntimeError(f'El servidor local del puerto {port} no superó la comprobación HTTPS.') from error
            time.sleep(0.25)
    raise RuntimeError(f'El servidor local del puerto {port} terminó antes de estar listo.')


def choose_port():
    with socket.socket() as local:
        local.bind((HOST, 0))
        return local.getsockname()[1]


def activate(script, label):
    process = launch(script, PORT, label)
    try:
        assets = ready(process, PORT, check_assets=True)
        if active_process(process.pid) != (process.pid, script):
            raise RuntimeError('El puerto no corresponde a la versión que se acaba de iniciar.')
    except Exception:
        if process.poll() is None:
            stop_tree(process.pid)
        raise
    PID_FILE.write_text(f'{process.pid}\n', encoding='utf-8')
    return assets


def deploy(archive):
    previous = active_process()
    release, digest = stage_release(archive)
    if previous:
        # El servicio anterior sigue disponible mientras se verifica el candidato.
        checked(release, 'manage.py', 'migrate', '--check', '--settings=config.settings.provisioning')
        checked(release, 'manage.py', 'collectstatic', '--noinput', '--verbosity=0',
                '--settings=config.settings.production')
    else:
        checked(release, 'scripts/arranque_seguro.py', '--solo-preparar')
    candidate_port = choose_port()
    candidate = launch(release / SERVER, candidate_port, 'deploy_candidate')
    try:
        assets = ready(candidate, candidate_port, check_assets=True)
        verification = json.loads(checked(release, 'scripts/verificar_https.py', '--puerto',
                                          str(candidate_port), port=candidate_port))
    finally:
        if candidate.poll() is None:
            stop_tree(candidate.pid)
    if active_process() != previous:
        raise RuntimeError('El proceso de demostración cambió durante la verificación.')
    if previous:
        stop_tree(previous[0])
    try:
        active_assets = activate(release / SERVER, 'deploy_active')
    except Exception:
        if previous:
            activate(previous[1], 'deploy_recovered')
        raise
    return {
        'fecha_utc': datetime.now(timezone.utc).isoformat(),
        'sha256_zip': digest,
        'version_extraida': release.relative_to(ROOT).as_posix(),
        'puerto_candidato': candidate_port,
        'recursos_candidato_https_200': assets,
        'verificacion_candidato': verification,
        'demo_activa': f'https://{HOST}:{PORT}/ingresar/',
        'recursos_demo_https_200': active_assets,
    }


def desplegar(archive):
    """Activa la versión verificada y registra la evidencia en dist."""
    if os.name != 'nt':
        raise RuntimeError('El despliegue local está preparado para Windows.')
    import msvcrt

    RUNTIME.mkdir(exist_ok=True)
    DIST.mkdir(exist_ok=True)
    with (RUNTIME / 'deploy.lock').open('a+b') as lock:
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise RuntimeError('Ya hay un despliegue local en curso.') from None
        result = deploy(Path(archive).resolve(strict=True))
        output = DIST / 'despliegue_local.json'
        staged = output.with_suffix('.json.tmp')
        staged.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        staged.replace(output)
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archivo', type=Path, required=True, help='ZIP generado por el proceso de entrega.')
    args = parser.parse_args()
    try:
        print(json.dumps(desplegar(args.archivo), ensure_ascii=False, indent=2))
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f'No se completó el despliegue. {error}\n')
