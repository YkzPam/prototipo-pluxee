from django.apps import AppConfig


class BeneficiosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'beneficios'
    verbose_name = 'Beneficios académicos'

    def ready(self):
        from . import signals  # noqa: F401
