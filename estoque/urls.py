from django.urls import path
from . import views

urlpatterns = [
    path('', views.listar_produtos, name='listar_produtos'),
    path('produto/novo/', views.cadastrar_produto, name='cadastrar_produto'),
    path('produto/<int:produto_id>/', views.detalhe_produto, name='detalhe_produto'),
    path('produto/<int:produto_id>/excluir/', views.excluir_produto, name='excluir_produto'),
    path('produto/<int:produto_id>/movimentacao/', views.registrar_movimentacao, name='registrar_movimentacao'),
]
