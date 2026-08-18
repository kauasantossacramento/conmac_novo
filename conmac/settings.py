from pathlib import Path
import environ, os
BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env(DEBUG=(bool, True))
environ.Env.read_env(env_file=os.path.join(BASE_DIR, ".env"))

SECRET_KEY = env("SECRET_KEY", default="dev-insecure")
DEBUG = env("DEBUG", default=True)

ALLOWED_HOSTS = ["192.168.200.152:8000", "192.168.200.152", "*"]

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "django_filters",
    "push_notifications",
    "despesas.apps.DespesasConfig",
    "webpush",

    'django.contrib.humanize',
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    #"django.middleware.clickjacking.XFrameOptionsMiddleware",
]

AUTHENTICATION_BACKENDS = [
    "despesas.auth_backends.CPFOrUsernameBackend",
    "django.contrib.auth.backends.ModelBackend",  # fallback
]

OMIE_APP_KEY = "6020274646386"
OMIE_APP_SECRET = "134901e41a4ef9a90f5813ba8fead742"

ROOT_URLCONF = "conmac.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {
        "context_processors": [
            "django.template.context_processors.debug",
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
            "conmac.context_processors.vapid_keys",
        ],
    },
}]
WSGI_APPLICATION = "conmac.wsgi.application"

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {
            # Aumenta o tempo de espera pelo desbloqueio para 20 segundos
            'timeout': 20,
        }
    }
}

AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = 'pt-br'
USE_THOUSAND_SEPARATOR = True
TIME_ZONE = "America/Bahia"
USE_I18N = True
USE_TZ = True



STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')




DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "login"


# Recomendado: leia chaves de variáveis de ambiente
import os

'''

"publicKey": "BO0H9-zL97jYyzcyVspuLLiMaQH8edrGA9dCIhqlZhjNlaJaLFAdyr3T-LGPULuJpbTjY_8foVNpsMVkQF5kAEI",
"privateKey": "9LCknL_JS0nZTgZVb7lTSYUNnDeJRhfsaHNWskr8JFY"
sujeito": "mailto: <kaua@conmac.com.br>
'''

PUSH_NOTIFICATIONS_SETTINGS = {
    "WP_PRIVATE_KEY": os.environ.get("VAPID_PRIVATE_KEY", "MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQg/j5jnfwS3R9kLr/Z7nyqUTIhbHXO534zvsAxDSIYs2ehRANCAAQnxIWToL7R+L7/mzpPI21YhpYGoK4I6ngQ5hf5yUf/3Sl5chwXJFde27ePaj51BF1EWSnNKNLVLA4nhQ1+N9/3"),
    "APP_SERVER_KEY": os.environ.get("VAPID_PUBLIC_KEY", "BCfEhZOgvtH4vv-bOk8jbViGlgagrgjqeBDmF_nJR__dKXlyHBckV17bt49qPnUEXURZKc0o0tUsDieFDX433_c"),
    "WP_CLAIMS": {"sub": "mailto:kaua@conmac.com.br"},
    "UPDATE_ON_DUPLICATE_REG_ID": True,
}


WEBPUSH_SETTINGS = {
    "VAPID_PUBLIC_KEY": "BLpTxDWt3BKMN1PAwSB1sp0CB0WQe0FQCdojvYEYSi2Vg8-kR6ivMvwZmLlqEmigdA1bKXGsevqUXDm7cDhgMm8",
    "VAPID_PRIVATE_KEY": "v8J_JS5KvSckJA8F8rdPt7gWdK4IvYhGtRgg1pdY4jE",
    "VAPID_ADMIN_EMAIL": "kaua@conmac.com.br"
}



import os
import json


# caminho para service account JSON (defina este env var no PythonAnywhere)
FIREBASE_SERVICE_ACCOUNT = os.environ.get("FIREBASE_SERVICE_ACCOUNT", "/home/conmac/gestao-inteligente-conmac/conmac-app-firebase-adminsdk-fbsvc-89ccdd6f2a.json")


'''
# O firebase web config (o que você copia do console quando cria o Web App)
# Exemplo (substitua pelos valores do seu projeto):
FIREBASE_CONFIG = {
    "apiKey": os.environ.get("FIREBASE_APIKEY", "AIzaSyDIJm4fS7o1m7VgvfFU-9WpIi0i-uKUyug"),
    "authDomain": os.environ.get("FIREBASE_AUTHDOMAIN", "conmac-app.firebaseapp.com"),
    "projectId": os.environ.get("FIREBASE_PROJECTID", "conmac-app"),
    "storageBucket": os.environ.get("FIREBASE_STORAGEBUCKET", "conmac-app.firebasestorage.app"),
    "messagingSenderId": os.environ.get("FIREBASE_MESSAGING_SENDER_ID", "199472856868"),
    "appId": os.environ.get("FIREBASE_APPID", "1:199472856868:web:7bd0fb536fbe63d9007db1"),
}
'''

# Public VAPID key (web push public key) — também pode vir do Project settings → Cloud Messaging
FIREBASE_VAPID_KEY = os.environ.get("FIREBASE_VAPID_KEY", "BDtArjaAYv_1Ljbm0I1a9X2Ina9o9XZP9TeUR0AN-Dl_xWClyGGvmHHM_oyDSvZctDq8RpajKemZaeO65HPrwl4")


# settings.py

import os

# ... outras configurações ...

# Mapeando a variável do PythonAnywhere para o nome que seu apps.py espera
FIREBASE_CREDENTIALS_FILE = "/home/conmac/gestao-inteligente-conmac/conmac-app-firebase-adminsdk-fbsvc-89ccdd6f2a.json"
# ── E-MAIL (cPanel / Webmail) ─────────────────────────────
EMAIL_BACKEND       = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST          = 'mail.conmac.com.br'
EMAIL_PORT          = 465
EMAIL_USE_TLS       = False   # ← False quando usar SSL
EMAIL_USE_SSL       = True    # ← SSL na porta 465
EMAIL_HOST_USER     = 'notas@conmac.com.br'
EMAIL_HOST_PASSWORD = 'notas@conmac!A'
DEFAULT_FROM_EMAIL  = 'CONMAC <notas@conmac.com.br>'


# ──────────────────────────────────────────────
# Configuração IMAP – Monitor de Cobranças
# Adicione estas linhas ao seu settings.py
# ──────────────────────────────────────────────

IMAP_HOST     = 'mail.conmac.com.br'
IMAP_PORT     =  993        # IMAP sobre SSL
IMAP_USER     = 'airam@conmac.com.br'
IMAP_PASSWORD = 's^EDJ7uvyI(q'


