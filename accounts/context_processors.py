from django.conf import settings
from django.utils.functional import SimpleLazyObject

from .demo import demo_user


def auth_options(request) -> dict:
    """Options for the login and sign-up pages.

    - google_login_enabled: show "Continue with Google" once its OAuth keys are set.
    - demo_account: the demo login details, if the demo account exists. Lazy, so the
      lookup only runs on pages that actually show the demo panel.
    """

    def demo_account():
        if demo_user() is None:
            return {}
        return {"email": settings.DEMO_EMAIL, "password": settings.DEMO_PASSWORD}

    return {
        "google_login_enabled": bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET),
        "demo_account": SimpleLazyObject(demo_account),
    }
