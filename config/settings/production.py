from .base import *

from django.core.exceptions import ImproperlyConfigured


DEBUG = env_bool("DJANGO_DEBUG", False)

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")

if not SECRET_KEY:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be set when using production settings."
    )

try:
    from .local import *
except ImportError:
    pass
