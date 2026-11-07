"""Datos locales compartidos entre las versiones empaquetadas del prototipo."""
import os
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME = CODE_ROOT / '.runtime'


def runtime_directory():
    configured = os.environ.get('PLUXEE_RUNTIME_DIR')
    if not configured:
        return DEFAULT_RUNTIME
    path = Path(configured)
    if not path.is_absolute() or path.name != '.runtime' or path.resolve() != path:
        raise ValueError('El directorio de datos de la demostración no es válido.')
    if path != DEFAULT_RUNTIME and not CODE_ROOT.is_relative_to(path / 'releases'):
        raise ValueError('El directorio de datos solo se comparte con versiones de esta demostración.')
    return path


RUNTIME_DIR = runtime_directory()
