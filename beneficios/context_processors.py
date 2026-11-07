from django.conf import settings


def project_context(request):
    return {'environment_label': settings.ENVIRONMENT_LABEL,
            'session_idle_minutes': settings.SESSION_IDLE_SECONDS // 60,
            'session_max_hours': settings.SESSION_MAX_SECONDS // 3600}
