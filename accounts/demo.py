"""The public demo account: lets visitors try TaskForge without signing up."""

from django.conf import settings
from django.contrib.auth import get_user_model


def demo_user():
    """The seeded demo user, or None if the demo is switched off or hasn't been seeded."""
    if not settings.DEMO_LOGIN_ENABLED:
        return None
    return (
        get_user_model().objects.filter(email__iexact=settings.DEMO_EMAIL, is_active=True).first()
    )
