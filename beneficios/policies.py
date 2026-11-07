"""Singleton de configuración inmutable por proceso, nunca de usuarios o sesiones."""
from functools import lru_cache
from dataclasses import dataclass
from django.conf import settings


@dataclass(frozen=True)
class SessionPolicy:
    idle_seconds: int
    max_seconds: int


@lru_cache(maxsize=4)
def _session_policy(idle_seconds, max_seconds):
    return SessionPolicy(idle_seconds, max_seconds)


def session_policy():
    return _session_policy(settings.SESSION_IDLE_SECONDS, settings.SESSION_MAX_SECONDS)
