#!/usr/bin/env python
"""Utilitário de linha de comando do Django."""
import os
import sys


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'estoque_project.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Não foi possível importar o Django. Verifique se ele está "
            "instalado e disponível na variável de ambiente PYTHONPATH. "
            "Você esqueceu de ativar o ambiente virtual?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
