from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Produto, Movimentacao


def listar_produtos(request):
    termo = request.GET.get('q', '')
    produtos = Produto.objects.all()
    if termo:
        produtos = produtos.filter(nome__icontains=termo)
    return render(request, 'estoque/listar_produtos.html', {
        'produtos': produtos,
        'termo': termo,
    })


def cadastrar_produto(request):
    if request.method == 'POST':
        Produto.objects.create(
            nome=request.POST['nome'],
            categoria=request.POST.get('categoria', ''),
            preco=request.POST['preco'],
            quantidade_minima=request.POST.get('quantidade_minima', 0),
        )
        messages.success(request, 'Produto cadastrado com sucesso.')
        return redirect('listar_produtos')
    return render(request, 'estoque/cadastrar_produto.html')


def detalhe_produto(request, produto_id):
    produto = get_object_or_404(Produto, id=produto_id)
    movimentacoes = produto.movimentacoes.order_by('-data')
    return render(request, 'estoque/detalhe_produto.html', {
        'produto': produto,
        'movimentacoes': movimentacoes,
    })


def excluir_produto(request, produto_id):
    produto = get_object_or_404(Produto, id=produto_id)

    if request.method == 'POST':
        nome = produto.nome
        produto.delete()
        messages.success(request, f'Produto "{nome}" excluído.')
        return redirect('listar_produtos')

    return render(request, 'estoque/excluir_produto.html', {'produto': produto})


def registrar_movimentacao(request, produto_id):
    produto = get_object_or_404(Produto, id=produto_id)

    if request.method == 'POST':
        tipo = request.POST['tipo']
        quantidade = int(request.POST['quantidade'])
        motivo = request.POST.get('motivo', '')

        if tipo == Movimentacao.SAIDA and quantidade > produto.quantidade_atual:
            messages.error(request, 'Quantidade de saída maior que o estoque disponível.')
            return redirect('detalhe_produto', produto_id=produto.id)

        Movimentacao.objects.create(
            produto=produto,
            tipo=tipo,
            quantidade=quantidade,
            motivo=motivo,
        )
        messages.success(request, 'Movimentação registrada.')
        return redirect('detalhe_produto', produto_id=produto.id)

    return render(request, 'estoque/registrar_movimentacao.html', {'produto': produto})
