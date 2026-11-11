from django.conf import settings
from django.db import DatabaseError
from .models import Notification
from .policies import session_policy


def project_context(request):
    return {'environment_label': settings.ENVIRONMENT_LABEL,
            'session_idle_minutes': session_policy().idle_seconds // 60,
            'session_max_hours': settings.SESSION_MAX_SECONDS // 3600}


def notification_context(request):
    if not request.user.is_authenticated:
        return {}
    try:
        count = Notification.objects.filter(user=request.user, read_at__isnull=True).count()
    except DatabaseError:
        count = None
    return {'notification_unread_count': count}
