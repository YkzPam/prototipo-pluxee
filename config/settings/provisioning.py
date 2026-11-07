"""Perfil exclusivo para preparar el esquema MySQL desde la consola local."""
from .production import *
from config.vault import load_vault

DATABASES = build_databases(load_vault(), provisioner=True)
