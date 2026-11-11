"""Verifica, empaqueta y, si se solicita, despliega el prototipo en este equipo."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import os
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'
DIST.mkdir(exist_ok=True)
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--desplegar', action='store_true',
                    help='Comprueba el ZIP y activa esa versión en la demostración HTTPS de Windows.')
args = parser.parse_args()
log = [f'Verificación local UTC: {datetime.now(timezone.utc).isoformat()}\n']
child_environment = os.environ.copy()
child_environment.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
steps = [
    [sys.executable, 'manage.py', 'check', '--settings=config.settings.testing'],
    [sys.executable, '-m', 'coverage', 'run', 'manage.py', 'test', '--settings=config.settings.testing'],
    [sys.executable, '-m', 'coverage', 'report', '--fail-under=80'],
    [sys.executable, 'manage.py', 'makemigrations', '--check', '--dry-run', '--settings=config.settings.testing'],
    [sys.executable, 'manage.py', 'collectstatic', '--noinput', '--settings=config.settings.testing'],
]
def run(command):
    result = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding='utf-8', errors='replace', env=child_environment)
    label = ' '.join(command[1:])
    log.extend([f'\n$ python {label}\n', result.stdout, f'Código de salida: {result.returncode}\n'])
    print(result.stdout, flush=True)
    if result.returncode:
        (DIST / 'verificacion_local.txt').write_text(''.join(log), encoding='utf-8')
        raise SystemExit(result.returncode)


for command in steps:
    run(command)

allowed_folders = {'beneficios', 'config', 'identidad', 'static', 'templates', 'scripts', '.github', 'docs'}
allowed_files = {'README.md', 'requirements.txt', 'manage.py', 'servidor.py',
                 'servidor_seguro.py', 'iniciar.cmd', 'preparar.cmd', 'verificar.cmd', '.coveragerc', '.gitignore'}
ignored = {'__pycache__', '.venv', '.runtime', '.git', '.static', 'dist', 'evidencias', '.evidencias'}
archive = DIST / 'Prototipo_Pluxee_Chile.zip'
partial = archive.with_suffix('.zip.tmp')
files = [ROOT / name for name in allowed_files]
for folder in allowed_folders:
    files.extend((ROOT / folder).rglob('*'))
try:
    with zipfile.ZipFile(partial, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for file in sorted(files):
            relative = file.relative_to(ROOT)
            if not file.is_file() or any(part in ignored for part in relative.parts):
                continue
            if file.suffix.lower() in {'.pyc', '.sqlite3', '.key', '.pem', '.dpapi', '.crt', '.cer'} or file.name == '.env':
                continue
            bundle.write(file, Path('Prototipo_Pluxee_Chile') / relative)
    with zipfile.ZipFile(partial) as bundle:
        if bundle.testzip() is not None:
            raise RuntimeError('El paquete no superó la comprobación de integridad.')
    partial.replace(archive)
finally:
    partial.unlink(missing_ok=True)
log.append(f'\nPaquete generado correctamente: {archive.name}\n')
if args.desplegar:
    run([sys.executable, 'scripts/desplegar_demo.py', '--archivo', str(archive)])
(DIST / 'verificacion_local.txt').write_text(''.join(log), encoding='utf-8')
print(f'Paquete verificado: {archive}', flush=True)
