from .base import *  # noqa: F403

DEBUG = True

# Signup, verification and password reset emails are printed to the terminal.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
