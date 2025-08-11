"""Pytest configuration for django-rest-framework-mcp tests."""

import django
from django.conf import settings


def pytest_configure(config):
    """Configure Django settings for pytest."""
    settings.configure(
        DEBUG=True,
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:'
            }
        },
        SECRET_KEY='test-secret-key-for-testing-only',
        USE_TZ=True,
        STATIC_URL='/static/',
        ROOT_URLCONF='tests.urls',
        TEMPLATES=[
            {
                'BACKEND': 'django.template.backends.django.DjangoTemplates',
                'APP_DIRS': True,
                'OPTIONS': {
                    'debug': True,
                }
            },
        ],
        MIDDLEWARE=[
            'django.middleware.common.CommonMiddleware',
            'django.contrib.sessions.middleware.SessionMiddleware',
            'django.contrib.auth.middleware.AuthenticationMiddleware',
            'django.contrib.messages.middleware.MessageMiddleware',
        ],
        INSTALLED_APPS=[
            'django.contrib.admin',
            'django.contrib.auth',
            'django.contrib.contenttypes',
            'django.contrib.sessions',
            'django.contrib.messages',
            'django.contrib.staticfiles',
            'rest_framework',
            'djangorestframework_mcp',
            'tests',
        ],
        PASSWORD_HASHERS=[
            'django.contrib.auth.hashers.MD5PasswordHasher',
        ],
        DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
        REST_FRAMEWORK={
            'DEFAULT_AUTHENTICATION_CLASSES': [],
            'DEFAULT_PERMISSION_CLASSES': [],
        }
    )
    
    django.setup()
    
    # Run migrations for test models
    from django.core.management import call_command
    call_command('migrate', '--run-syncdb', verbosity=0)