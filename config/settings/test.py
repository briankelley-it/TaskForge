from .base import *  # noqa: F403

DEBUG = False

# The default hasher is slow on purpose. Tests create many users, so use a fast one.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
