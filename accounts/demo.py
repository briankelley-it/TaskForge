"""The public demo account: lets visitors try TaskForge without signing up."""

from django.conf import settings
from django.contrib.auth import get_user_model


def demo_details() -> tuple[str, str] | None:
    """(email, password) for the demo, or None when it's switched off or not configured.

    getattr with defaults: a settings module without the DEMO_* values (an older copy, or a
    project that never set them) simply hides the demo instead of crashing the auth pages.
    """
    if not getattr(settings, "DEMO_LOGIN_ENABLED", False):
        return None
    email = getattr(settings, "DEMO_EMAIL", "")
    password = getattr(settings, "DEMO_PASSWORD", "")
    return (email, password) if email else None


def demo_user():
    """The seeded demo user, or None if the demo is switched off or hasn't been seeded."""
    details = demo_details()
    if details is None:
        return None
    return get_user_model().objects.filter(email__iexact=details[0], is_active=True).first()
