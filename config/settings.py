"""
Project settings for the inventory management system.
"""
from datetime import timedelta
from pathlib import Path
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

# Lido do .env (nunca commitado - ver .gitignore) em vez de fixo no
# código. Sem default: se o .env não existir, falha ao subir em vez
# de silenciosamente usar uma chave fraca.
SECRET_KEY = config('SECRET_KEY')

DEBUG = config('DEBUG', default=False, cast=bool)

# Em produção, o Render passa o(s) domínio(s) reais via variável de
# ambiente. Em dev local a variável não é setada, então cai no default
# abaixo - sem isso o runserver local para de funcionar (Django rejeita
# qualquer Host header que não esteja na lista).
ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    default='127.0.0.1,localhost',
    cast=lambda v: [host.strip() for host in v.split(',')],
)

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'axes',
    'inventory',
]

# axes precisa entrar ANTES do ModelBackend padrão do Django - é ele
# quem intercepta a tentativa de login e barra antes mesmo de checar a
# senha, se o limite de tentativas falhas já foi atingido.
AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# Bloqueio de login por força bruta: depois de 5 tentativas erradas
# (username+IP), a conta fica bloqueada por 30 minutos - mesmo que a
# próxima tentativa use a senha certa.
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=30)
AXES_LOCKOUT_PARAMETERS = ['username', 'ip_address']
# Sem isso, a tela de bloqueio é o texto cru padrão do pacote ("Account
# locked...") - fora do padrão visual do resto do site (mesmo motivo
# de termos criado 403.html/404.html/500.html customizados).
AXES_LOCKOUT_TEMPLATE = 'lockout.html'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # Precisa vir logo depois do SecurityMiddleware e antes de tudo
    # mais - é o whitenoise servindo os arquivos estáticos (CSS/JS)
    # direto do Django em produção, sem precisar de nginx/S3.
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    # Precisa vir depois da AuthenticationMiddleware (usa request.user).
    'inventory.middleware.ForcePasswordChangeMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Precisa ser o último middleware da lista - exigência do próprio
    # django-axes, pra garantir que ele veja a resposta final da
    # tentativa de autenticação antes de decidir bloquear ou não.
    'axes.middleware.AxesMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'inventory.context_processors.gestor_flag',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Banco de dados: PostgreSQL (Neon), lido do .env - a branch
# `development` localmente, a branch `production` no deploy (Render).
# sslmode/channel_binding exigidos pelo Neon, passados via OPTIONS
# (parâmetros extras repassados direto pro driver psycopg).
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST'),
        'PORT': config('DB_PORT', default='5432'),
        'OPTIONS': {
            'sslmode': 'require',
            'channel_binding': 'require',
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Auth redirects: PRD §6.4 requires login for every write action, and
# the product owner chose login-required for the listing too, so there
# is no public route left - every view redirects here when anonymous.
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'product_list'
LOGOUT_REDIRECT_URL = 'login'

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
# Onde `collectstatic` (rodado no build do Render) reúne os arquivos
# estáticos pra servir - precisa existir pro whitenoise funcionar.
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        # A versão com manifesto (hash no nome do arquivo, cache-busting
        # automático) exige que `collectstatic` já tenha rodado - isso só
        # acontece no build de produção. Localmente (DEBUG=True, sem
        # collectstatic) usa o storage simples, senão até os testes
        # quebram tentando resolver {% static %} sem manifesto.
        'BACKEND': (
            'django.contrib.staticfiles.storage.StaticFilesStorage'
            if DEBUG else
            'whitenoise.storage.CompressedManifestStaticFilesStorage'
        ),
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Settings de segurança que só fazem sentido em produção (DEBUG=False).
# Se não fossem condicionados a `not DEBUG`, forçar HTTPS quebraria o
# ambiente de desenvolvimento local, que roda em HTTP simples.
if not DEBUG:
    # O Render termina o HTTPS na borda e repassa a requisição pro
    # nosso app por HTTP simples internamente, avisando com esse header
    # que a requisição original era HTTPS. Sem isso, SECURE_SSL_REDIRECT
    # entraria num loop infinito de redirecionamento.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # HSTS: instrui o navegador a sempre usar HTTPS nesse domínio pelos
    # próximos N segundos, mesmo que alguém digite http:// na barra de
    # endereço. Começa baixo (1h) de propósito - é uma configuração que
    # "gruda" no navegador do usuário pelo tempo configurado, então só
    # sobe esse número depois de confirmar que o HTTPS está estável.
    SECURE_HSTS_SECONDS = 3600
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
