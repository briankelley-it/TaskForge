from django.conf import settings


def auth_options(request) -> dict:
    """Whether to show "Continue with Google" (only once its OAuth keys are configured)."""
    return {
        "google_login_enabled": bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)
    }
