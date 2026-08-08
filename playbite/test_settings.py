from .settings import *

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'test_db.sqlite3',
    }
}

PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

MIGRATION_MODULES = {
    'accounts': None,
    'marketing': None,
    'restaurants': None,
    'customer': None,
    'games': None,
    'coupons': None,
    'analytics_dashboard': None,
    'staff': None,
}
