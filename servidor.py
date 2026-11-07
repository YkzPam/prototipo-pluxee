"""Servidor local del prototipo. No expone el equipo a la red."""
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
from config.wsgi import application
from waitress import serve

if __name__ == '__main__':
    port = int(os.environ.get('PROTOTYPE_PORT', '8765'))
    print('\nPrototipo académico Pluxee Chile', flush=True)
    print(f'Dirección: http://127.0.0.1:{port}', flush=True)
    print('Solo datos ficticios. Ctrl+C detiene el servidor.\n', flush=True)
    serve(application, host='127.0.0.1', port=port, threads=6)
