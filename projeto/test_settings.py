"""Test settings that preserve production security configuration by default."""

from .settings import *  # noqa: F403

# The test client uses HTTP unless explicitly configured for HTTPS. Keep
# SecurityMiddleware, CSRF middleware, and the production cookie settings intact;
# only prevent the production HTTPS redirect from short-circuiting view tests.
SECURE_SSL_REDIRECT = False
DEBUG = True

# Test storage: use local FileSystemStorage so tests do not depend on
# Cloudinary (which requires credentials not available in test environment).
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}
