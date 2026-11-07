"""Pipeline local: verificar el código y preparar un ZIP sin bases ni secretos."""
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import os
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'
DIST.mkdir(exist_ok=True)
log = [f'Verificación local UTC: {datetime.now(timezone.utc).isoformat()}\n']
child_environment = os.environ.copy()
child_environment.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
steps = [
    [sys.executable, 'manage.py', 'check', '--settings=config.settings.testing'],
    [sys.executable, '-m', 'coverage', 'run', 'manage.py', 'test', '--settings=config.settings.testing'],
    [sys.executable, '-m', 'coverage', 'report', '--fail-under=80'],
    [sys.executable, 'manage.py', 'makemigrations', '--check', '--dry-run'],
    [sys.executable, 'manage.py', 'collectstatic', '--noinput'],
]
for command in steps:
    result = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding='utf-8', errors='replace', env=child_environment)
    label = ' '.join(command[1:])
    log.extend([f'\n$ python {label}\n', result.stdout, f'Código de salida: {result.returncode}\n'])
    print(result.stdout, flush=True)
    if result.returncode:
        (DIST / 'verificacion_local.txt').write_text(''.join(log), encoding='utf-8')
        raise SystemExit(result.returncode)

allowed_folders = {'beneficios', 'config', 'static', 'templates', 'scripts', '.github'}
allowed_files = {'README.md', 'requirements.txt', 'manage.py', 'servidor.py',
                 'iniciar.cmd', 'preparar.cmd', 'verificar.cmd', '.coveragerc', '.gitignore'}
ignored = {'__pycache__', '.venv', '.runtime', '.git', '.static', 'dist', 'evidencias', '.evidencias'}
archive = DIST / 'Prototipo_Pluxee_Chile.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
    for file in sorted(ROOT.rglob('*')):
        relative = file.relative_to(ROOT)
        if not file.is_file() or any(part in ignored for part in relative.parts):
            continue
        if relative.parts[0] not in allowed_folders and str(relative) not in allowed_files:
            continue
        if file.suffix.lower() in {'.pyc', '.sqlite3', '.key', '.pem'} or file.name == '.env':
            continue
        bundle.write(file, Path('Prototipo_Pluxee_Chile') / relative)
with zipfile.ZipFile(archive) as bundle:
    if bundle.testzip() is not None:
        raise RuntimeError('El paquete no superó la comprobación de integridad.')
log.append(f'\nPaquete generado correctamente: {archive.name}\n')
(DIST / 'verificacion_local.txt').write_text(''.join(log), encoding='utf-8')
print(f'Paquete verificado: {archive}', flush=True)
