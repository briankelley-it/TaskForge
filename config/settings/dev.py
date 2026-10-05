from .base import *  # noqa: F403
from .base import INSTALLED_APPS, MIDDLEWARE

DEBUG = True

# Signup, verification and password reset emails are printed to the terminal.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Live reload: the open browser tab refreshes itself whenever a template, static file
# (including the CSS the Tailwind watcher rebuilds) or Python file changes.
# Development only, so it's not in base.py and isn't installed in the production image.
INSTALLED_APPS = [*INSTALLED_APPS, "django_browser_reload"]
MIDDLEWARE = [*MIDDLEWARE, "django_browser_reload.middleware.BrowserReloadMiddleware"]
