import os
from .settings import *  # noqa: F401,F403

# Force no Gemini key so AI tests use the offline rule-based fallback.
os.environ['GEMINI_API_KEY'] = ''
GEMINI_API_KEY = ''

# Disable the APScheduler on test runs.
SRMS_RUN_SCHEDULER = False

# Faster, isolated database for the test runner.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Tests use an in-memory DB, which cannot host the DatabaseCache backend.
# Use an in-memory cache so the rate-limit tests run in isolation.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'test-cache',
    }
}

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]
