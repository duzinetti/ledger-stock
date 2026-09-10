import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Cria o superusuário de produção lendo usuário/senha de variáveis
    de ambiente - feito pra rodar sozinho no comando de build a cada
    deploy, já que o tier gratuito do Render não tem Shell/SSH pra
    rodar `createsuperuser` manualmente. Sempre confere se já existe
    algum superusuário antes de criar, pra ser seguro de rodar de
    novo em todo deploy seguinte sem tentar recriar (ou dar erro).
    """

    help = (
        'Cria um superusuário a partir de DJANGO_SUPERUSER_USERNAME/'
        'DJANGO_SUPERUSER_PASSWORD, apenas se ainda não existir nenhum.'
    )

    def handle(self, *args, **options):
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write('Já existe superusuário - nada a fazer.')
            return

        username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        if not username or not password:
            self.stdout.write(self.style.WARNING(
                'DJANGO_SUPERUSER_USERNAME/DJANGO_SUPERUSER_PASSWORD não '
                'configurados - superusuário não criado.'
            ))
            return

        User.objects.create_superuser(username=username, password=password)
        self.stdout.write(self.style.SUCCESS(f'Superusuário "{username}" criado.'))
