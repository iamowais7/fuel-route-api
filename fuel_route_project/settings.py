import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-fuel-route-dev-key-change-in-production')

DEBUG = os.getenv('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '*').split(',')

INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'rest_framework',
    'route_api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.common.CommonMiddleware',
]

ROOT_URLCONF = 'fuel_route_project.urls'

WSGI_APPLICATION = 'fuel_route_project.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
}

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

FUEL_PRICES_CSV = os.getenv('FUEL_PRICES_CSV', str(BASE_DIR / 'route_api' / 'data' / 'fuel_prices.csv'))

TANK_CAPACITY_MILES = float(os.getenv('TANK_CAPACITY_MILES', '500'))
VEHICLE_MPG = float(os.getenv('VEHICLE_MPG', '10'))
MAX_OFF_ROUTE_MILES = float(os.getenv('MAX_OFF_ROUTE_MILES', '5'))
