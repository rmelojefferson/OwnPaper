from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env_bool("DJANGO_DEBUG", True)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-p+ho0*@_sup-adki6cqar80uu+q((=d$fh7is9x)vxtbw3r^3g",
)

# SECURITY WARNING: define the correct hosts in production!
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["*"])

import os

EMAIL_BACKEND = os.getenv(
    "DJANGO_EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)

try:
    from .local import *
except ImportError:
    pass
