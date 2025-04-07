"""
Django settings for leadsAutomation project.

Generated by 'django-admin startproject' using Django 5.0.7.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/5.0/ref/settings/
"""

from pathlib import Path
from dotenv import load_dotenv
import dj_database_url
import os

load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-syzuy1&t#m7pny%j2x71-k^vwvde^9a^t8v7v_0z4%$vov*c7r')
# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True


BASE_URL = 'https://cleaningbizai.com'
ALLOWED_HOSTS = ['*']

# Trust Proxy Headers (Needed for Cloudflare)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Ensure Django Forces HTTPS
SECURE_SSL_REDIRECT = False
CSRF_COOKIE_SECURE = not DEBUG  # Secure CSRF Cookies in production
SESSION_COOKIE_SECURE = not DEBUG  # Secure Session Cookies in production

# Square Payment Configuration
SQUARE_APP_ID = os.getenv('SQUARE_APP_ID')
if not SQUARE_APP_ID:
    # Provide a default value for development or raise a warning
    if DEBUG:
        # For sandbox environment
        SQUARE_APP_ID = 'sandbox-sq0idp-your-sandbox-app-id'
        import warnings
        warnings.warn("SQUARE_APP_ID environment variable not set. Using default sandbox value.")
SQUARE_ACCESS_TOKEN = os.getenv('SQUARE_ACCESS_TOKEN')
SQUARE_LOCATION_ID = os.getenv('SQUARE_LOCATION_ID')
SQUARE_ENVIRONMENT = os.getenv('SQUARE_ENVIRONMENT', 'sandbox')

# Additional security settings for production
if not DEBUG:
    # HSTS settings
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
    # Content security
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = 'DENY'  # Prevents your site from being framed




INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'whitenoise.runserver_nostatic',  # Add WhiteNoise
    'django.contrib.staticfiles',
    'django_extensions',
    'sslserver',
    'django_q',
    'automation',
    'rest_framework',
    'corsheaders',
    'accounts',
    'bookings',
    'invoice',
    'integrations',
    'ai_agent',
    'usage_analytics',
    'subscription',
    'retell_agent',
    'admin_dashbaord'
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'accounts.middleware.BusinessApprovalMiddleware',  # Add business approval middleware
    'subscription.middleware.SubscriptionRequiredMiddleware',  # Add subscription middleware
]

ROOT_URLCONF = 'leadsAutomation.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'leadsAutomation.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    'default': dj_database_url.config(default=os.getenv('DATABASE_URL'))
}


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = 'static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CORS Settings
CORS_ALLOW_ALL_ORIGINS = True  # For development only
CORS_ALLOW_CREDENTIALS = True


CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


CSRF_TRUSTED_ORIGINS = ['http://localhost:8000','https://localhost:8000', 'https://ceocleaners.up.railway.app', 'https://ai.cleaningbizai.com', 'https://cleaningbizai.up.railway.app', 'https://127.0.0.1:8000', 'http://127.0.0.1:8000', 'https://cleaningbizai.com']


EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.zeptomail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('EMAIL_HOST_USER', '')

# Retell Settings
RETELL_API_KEY = os.getenv('RETELL_API_KEY', '')
RETELL_BASE_URL = 'https://api.retellai.com'

# settings.py example
Q_CLUSTER = {
    'name': 'cleaningbizai',
    'workers': 8,
    'recycle': 500,
    'timeout': 300,
    'retry': 3600,
    'compress': True,
    'save_limit': 250,
    'queue_limit': 500,
    'cpu_affinity': 4,
    'label': 'Django Q2',
    'orm': 'default',
    'max_attempts': 3,
}
