import uuid
from datetime import datetime, timezone as dt_timezone
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.utils import timezone
from .events import record
from .policies import session_policy
from .responses import RejectedResponseCreator


class SessionPolicyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = uuid.uuid4()
        if request.user.is_authenticated:
            now = timezone.now().timestamp()
            policy = session_policy()
            created = request.session.get('auth_started_at', now)
            last = request.session.get('last_activity_at', now)
            invalid = not isinstance(created, (int, float)) or not isinstance(last, (int, float))
            expired = invalid or now - created >= policy.max_seconds or now - last >= policy.idle_seconds
            if expired:
                reason = 'La sesión finalizó por inactividad.' if not invalid and now - last >= policy.idle_seconds else 'La sesión alcanzó su duración máxima y requiere un nuevo ingreso.'
                record(request, 'expired', 'expired', reason)
                logout(request)
                if request.path.startswith('/api/'):
                    return RejectedResponseCreator().create_response(request, reason, status='expired', http_status=401)
                messages.warning(request, reason)
                return redirect('ingresar')
            request.session['auth_started_at'] = created
            request.session['last_activity_at'] = now
            # El vencimiento absoluto no se extiende con navegación ni heartbeat.
            request.session.set_expiry(datetime.fromtimestamp(created + policy.max_seconds, tz=dt_timezone.utc))
        return self.get_response(request)


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['Content-Security-Policy'] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
            "form-action 'self'; frame-ancestors 'none'; base-uri 'self'; object-src 'none'"
        )
        response['Referrer-Policy'] = 'same-origin'
        response['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        if not request.path.startswith('/static/'):
            response['Cache-Control'] = 'no-store, private'
            response['Pragma'] = 'no-cache'
        return response
