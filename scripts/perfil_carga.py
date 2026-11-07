r"""Perfil reproducible RNF01/RNF02 contra Waitress local y una BD desechable.

Ejemplo: .venv\Scripts\python.exe scripts\perfil_carga.py
Por defecto: 20 sesiones, una consulta por usuario cada 5 s, durante 600 s.
La prueba utiliza exclusivamente cuentas y datos sintéticos. No evalúa la red
de Pluxee, disponibilidad mensual, HTTPS ni la experiencia de participantes.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timezone
from html.parser import HTMLParser
from http.cookiejar import CookieJar
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import socket
import statistics
import subprocess
import sys
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener
import uuid


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / '.runtime'
EVIDENCE = ROOT / '.evidencias'
FIXTURE_PASSWORD = 'CargaSoloPrueba2026!'


class CsrfParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.token = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'input' and attrs.get('name') == 'csrfmiddlewaretoken':
            self.token = attrs.get('value')


def prepare_fixture(count):
    """Se ejecuta en un proceso separado, apuntado solo a la BD creada aquí."""
    sys.path.insert(0, str(ROOT))
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.utils import timezone as django_timezone
    from beneficios.models import BenefitAccount, Movement, ServiceState
    rows = []
    with transaction.atomic():
        for i in range(count):
            username = f'carga_{i + 1:02d}'
            user = get_user_model().objects.create_user(
                username=username, password=FIXTURE_PASSWORD,
                first_name='Usuario de carga', last_name=f'Prueba {i + 1}')
            account = BenefitAccount.objects.create(user=user, number_suffix=f'{i + 1:04d}')
            now = django_timezone.now()
            items = []
            for kind, amount, description in [
                ('abono', 100000, 'Abono ficticio para la prueba de carga'),
                ('cargo', 5000, 'Compra ficticia uno'),
                ('cargo', 10000, 'Compra ficticia dos'),
            ]:
                movement = Movement.objects.create(
                    account=account, kind=kind, amount=amount,
                    description=description, occurred_at=now)
                items.append(movement.pk)
            rows.append({'username': username, 'account_id': account.pk,
                         'balance': 85000, 'movement_ids': sorted(items)})
        for code, label in [('balance', 'Saldo'), ('movements', 'Movimientos')]:
            ServiceState.objects.create(code=code, label=label, available=True)
    print(json.dumps(rows))


def public_versions():
    return {'python': platform.python_version(),
            'operating_system': platform.system(),
            'django': importlib.metadata.version('Django'),
            'waitress': importlib.metadata.version('waitress')}


def wait_ready(base_url, process):
    until = time.monotonic() + 30
    while time.monotonic() < until:
        if process.poll() is not None:
            raise RuntimeError('El servidor de la prueba finalizó antes de estar disponible.')
        try:
            with build_opener().open(base_url + '/ingresar/', timeout=2) as response:
                if response.status == 200:
                    return
        except (OSError, HTTPError, URLError):
            time.sleep(0.2)
    raise RuntimeError('El servidor local no estuvo disponible dentro del plazo de preparación.')


def authenticated_client(base_url, fixture):
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    with opener.open(base_url + '/ingresar/', timeout=30) as response:
        parser = CsrfParser()
        parser.feed(response.read().decode('utf-8'))
    if not parser.token:
        raise RuntimeError('El formulario local no entregó un token CSRF.')
    data = urlencode({'username': fixture['username'], 'password': FIXTURE_PASSWORD,
                      'csrfmiddlewaretoken': parser.token}).encode('utf-8')
    request = Request(base_url + '/ingresar/', data=data,
                      headers={'Referer': base_url + '/ingresar/', 'Origin': base_url})
    with opener.open(request, timeout=30) as response:
        response.read()
        if response.status != 200 or response.geturl().rstrip('/') == base_url + '/ingresar':
            raise RuntimeError('Una cuenta sintética no pudo iniciar sesión.')
    return opener


def validate_payload(payload, fixture, service):
    if not isinstance(payload, dict) or payload.get('status') != 'updated':
        return False
    data = payload.get('data')
    if not isinstance(data, dict):
        return False
    if service == 'saldo':
        return data.get('balance') == fixture['balance'] and data.get('currency') == 'CLP'
    items = data.get('items')
    return (isinstance(items, list) and data.get('total') == len(fixture['movement_ids'])
            and sorted(item.get('id') for item in items) == fixture['movement_ids'])


def percentile95(values):
    """Percentil empírico de rango más próximo (ceil(0,95*N))."""
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)] if ordered else None


def summarize(samples, args, expected):
    successful = [row for row in samples if row['ok']]
    durations = [row['elapsed_ms'] for row in successful]
    ratio = len(successful) / expected if expected else 0
    p95 = percentile95(durations)
    return {
        'expected_queries': expected, 'completed_queries': len(samples),
        'successful_queries': len(successful), 'failed_queries': len(samples) - len(successful),
        'missing_queries': expected - len(samples), 'success_ratio': ratio,
        'response_p95_ms_successful': p95,
        'response_mean_ms_successful': statistics.mean(durations) if durations else None,
        'response_max_ms_successful': max(durations) if durations else None,
        'queries_with_audit_not_confirmed': sum(row['audit_recorded'] is not True for row in samples),
        'queries_starting_over_one_interval_late': sum(row['schedule_lateness_ms'] > args.interval * 1000 for row in samples),
        'rnf01_target_success_99_percent_met': ratio >= 0.99 and len(samples) == expected,
        'rnf02_target_p95_at_most_3000_ms_met': p95 is not None and p95 <= 3000,
        'p95_method': 'Nearest rank: ordered successful latencies[ceil(0.95*N)-1]',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--users', type=int, default=20)
    parser.add_argument('--interval', type=float, default=5)
    parser.add_argument('--duration', type=float, default=600)
    parser.add_argument('--port', type=int, default=8767)
    parser.add_argument('--prepare-db', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not 1 <= args.users <= 50 or not 1 <= args.interval <= 60 or not 1 <= args.duration <= 3600:
        parser.error('Usuarios:1..50; intervalo:1..60s; duración:1..3600s.')
    if not 1024 <= args.port <= 65535 or args.port == 8765:
        parser.error('Se requiere un puerto local distinto del servidor principal 8765.')
    if args.prepare_db:
        prepare_fixture(args.users)
        return
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', args.port))
    RUNTIME.mkdir(exist_ok=True)
    EVIDENCE.mkdir(exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid.uuid4().hex[:8]
    db_path = (RUNTIME / f'carga_{run_id}.sqlite3').resolve()
    if db_path.parent != RUNTIME.resolve() or db_path.exists():
        raise RuntimeError('La ruta de datos de prueba no es una base nueva del directorio previsto.')
    result_path = EVIDENCE / f'perfil_carga_{run_id}.json'
    server_log = EVIDENCE / f'perfil_carga_{run_id}_servidor.log'
    samples_path = EVIDENCE / f'perfil_carga_{run_id}_muestras.ndjson'
    environment = os.environ.copy()
    environment.update({'DJANGO_SETTINGS_MODULE': 'config.settings.development',
                        'PLUXEE_DB': str(db_path), 'PROTOTYPE_PORT': str(args.port),
                        'SESSION_IDLE_SECONDS': '900', 'SESSION_MAX_SECONDS': '28800',
                        'PYTHONUTF8': '1', 'PYTHONUNBUFFERED': '1'})
    python = sys.executable
    print('Preparando base independiente y cuentas sintéticas...', flush=True)
    subprocess.run([python, 'manage.py', 'migrate', '--noinput', '--verbosity', '0'],
                   cwd=ROOT, env=environment, check=True)
    seed = subprocess.run([python, str(Path(__file__).resolve()), '--prepare-db', '--users', str(args.users)],
                          cwd=ROOT, env=environment, check=True, capture_output=True, text=True, encoding='utf-8')
    fixtures = json.loads(seed.stdout)
    base_url = f'http://127.0.0.1:{args.port}'
    samples = []
    samples_lock = threading.Lock()
    slots = math.ceil(args.duration / args.interval)
    expected = args.users * slots
    report = {
        'run_id': run_id, 'status': 'preparing',
        'configuration': {'users': args.users, 'query_interval_seconds_per_user': args.interval,
                          'duration_seconds': args.duration, 'slots_per_user': slots,
                          'expected_queries': expected, 'query_schedule': 't=0,interval,... < duration; saldo/movimientos alternated per user',
                          'waitress_threads': 6, 'base_url': base_url, 'database': str(db_path),
                          'database_isolation': 'New dedicated SQLite file; principal server/database not used',
                          'services_induced_unavailable': False},
        'environment': public_versions(),
        'scope': 'HTTP loopback with Waitress and synthetic data. No real Pluxee network, HTTPS, cloud, participant validation or monthly availability claim.',
        'samples_file': str(samples_path),
        'preconditions': {'authenticated_synthetic_users': 0, 'services_available': True},
    }
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    process = None
    try:
        with server_log.open('w', encoding='utf-8') as log, samples_path.open('w', encoding='utf-8') as sample_stream:
            process = subprocess.Popen([python, 'servidor.py'], cwd=ROOT, env=environment,
                                       stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
            wait_ready(base_url, process)
            clients = [(authenticated_client(base_url, fixture), fixture) for fixture in fixtures]
            report['preconditions']['authenticated_synthetic_users'] = len(clients)
            report['started_at_utc'] = datetime.now(timezone.utc).isoformat()
            start = time.monotonic() + 0.5
            end = start + args.duration
            report['status'] = 'running'
            report['last_checkpoint_at_utc'] = datetime.now(timezone.utc).isoformat()
            result_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f'Perfil iniciado: {args.users} usuarios, cada {args.interval:g}s, {args.duration:g}s, {expected} consultas; puerto {args.port}.', flush=True)

            def worker(client_index, opener, fixture):
                for slot in range(slots):
                    scheduled = start + slot * args.interval
                    remaining = scheduled - time.monotonic()
                    if remaining > 0:
                        time.sleep(remaining)
                    began = time.monotonic()
                    service = 'saldo' if slot % 2 == 0 else 'movimientos'
                    url = f'{base_url}/api/cuentas/{fixture["account_id"]}/{service}/'
                    row = {'user_index': client_index + 1, 'slot': slot,
                           'service': service, 'scheduled_offset_seconds': round(slot * args.interval, 6),
                           'started_offset_seconds': round(began - start, 6),
                           'schedule_lateness_ms': round(max(0, began - scheduled) * 1000, 3),
                           'http_status': None, 'application_status': None, 'audit_recorded': None,
                           'ok': False, 'error_kind': None}
                    try:
                        with opener.open(url, timeout=30) as response:
                            row['http_status'] = response.status
                            payload = json.loads(response.read())
                        row['application_status'] = payload.get('status') if isinstance(payload, dict) else None
                        row['audit_recorded'] = payload.get('audit_recorded') if isinstance(payload, dict) else None
                        row['ok'] = 200 <= row['http_status'] < 300 and validate_payload(payload, fixture, service)
                        if not row['ok']:
                            row['error_kind'] = 'unexpected_payload_or_status'
                    except HTTPError as error:
                        row['http_status'] = error.code
                        row['error_kind'] = 'http_error'
                        error.close()
                    except (URLError, TimeoutError, OSError, ValueError, TypeError, AttributeError) as error:
                        row['error_kind'] = type(error).__name__
                    row['elapsed_ms'] = round((time.monotonic() - began) * 1000, 3)
                    with samples_lock:
                        samples.append(row)
                        # Cada muestra queda persistida inmediatamente. Si un
                        # cierre externo mata el proceso, no se pierde toda la
                        # latencia HTTP acumulada hasta ese momento.
                        sample_stream.write(json.dumps(row, ensure_ascii=False) + '\n')
                        sample_stream.flush()
                remaining = end - time.monotonic()
                if remaining > 0:
                    time.sleep(remaining)

            with ThreadPoolExecutor(max_workers=args.users) as executor:
                futures = [executor.submit(worker, index, opener, fixture)
                           for index, (opener, fixture) in enumerate(clients)]
                pending = set(futures)
                while pending:
                    _, pending = wait(pending, timeout=30)
                    with samples_lock:
                        count = len(samples)
                        success = sum(row['ok'] for row in samples)
                        checkpoint_samples = list(samples)
                    report['last_checkpoint_at_utc'] = datetime.now(timezone.utc).isoformat()
                    report['summary'] = summarize(checkpoint_samples, args, expected)
                    checkpoint_path = result_path.with_suffix('.tmp')
                    checkpoint_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
                    checkpoint_path.replace(result_path)
                    print(f'Progreso: {min(args.duration, max(0, time.monotonic() - start)):.0f}s; consultas {count}/{expected}; correctas {success}.', flush=True)
                for future in futures:
                    future.result()
            report['actual_duration_seconds'] = round(time.monotonic() - start, 6)
            report['status'] = 'completed'
    except BaseException as error:
        report['status'] = 'interrupted' if isinstance(error, KeyboardInterrupt) else 'failed'
        report['error_kind'] = type(error).__name__
        raise
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        report['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        report['samples'] = sorted(samples, key=lambda row: (row['slot'], row['user_index']))
        report['summary'] = summarize(samples, args, expected)
        result_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'Evidencia: {result_path}', flush=True)
        print(json.dumps(report['summary'], ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
