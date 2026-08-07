from django.contrib import admin
from .models import Produto, Movimentacao


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'categoria', 'preco', 'quantidade_atual', 'quantidade_minima', 'estoque_baixo')
    search_fields = ('nome', 'categoria')


@admin.register(Movimentacao)
class MovimentacaoAdmin(admin.ModelAdmin):
    list_display = ('produto', 'tipo', 'quantidade', 'data', 'motivo')
    list_filter = ('tipo', 'data')
