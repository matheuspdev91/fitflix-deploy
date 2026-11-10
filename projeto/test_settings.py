"""Test settings that preserve production security configuration by default."""

from .settings import *  # noqa: F403

# The test client uses HTTP unless explicitly configured for HTTPS. Keep
# SecurityMiddleware, CSRF middleware, and the production cookie settings intact;
# only prevent the production HTTPS redirect from short-circuiting view tests.
SECURE_SSL_REDIRECT = False
DEBUG = True
