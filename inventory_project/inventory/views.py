from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Product, StockMovement
from .services import register_movement as register_movement_service
from .services import InsufficientStockError


def product_list(request):
    search_term = request.GET.get('q', '')

    # with_current_quantity() brings the calculated quantity in a
    # SINGLE query, instead of firing an aggregation query per
    # product (N+1) as would happen using the `current_quantity`
    # property inside the template loop.
    products = Product.objects.with_current_quantity().order_by('name')
    if search_term:
        products = products.filter(name__icontains=search_term)

    paginator = Paginator(products, 10)
    paginated_products = paginator.get_page(request.GET.get('page'))

    return render(request, 'inventory/product_list.html', {
        'products': paginated_products,
        'search_term': search_term,
    })


def product_create(request):
    if request.method == 'POST':
        Product.objects.create(
            name=request.POST['nome'],
            category=request.POST.get('categoria', ''),
            price=request.POST['preco'],
            minimum_quantity=request.POST.get('quantidade_minima', 0),
        )
        messages.success(request, 'Produto cadastrado com sucesso.')
        return redirect('product_list')
    return render(request, 'inventory/product_create.html')


def product_update(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if request.method == 'POST':
        product.name = request.POST['nome']
        product.category = request.POST.get('categoria', '')
        product.price = request.POST['preco']
        product.minimum_quantity = request.POST.get('quantidade_minima', 0)
        product.save()
        messages.success(request, 'Produto atualizado.')
        return redirect('product_detail', product_id=product.id)

    return render(request, 'inventory/product_update.html', {'product': product})


def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    # select_related('product') avoids N+1 when rendering the
    # history: without it, each listed movement would fire an extra
    # query to fetch the related product (used in __str__ and in the
    # template).
    movements = product.movements.select_related('product').order_by('-date')
    return render(request, 'inventory/product_detail.html', {
        'product': product,
        'movements': movements,
    })


def product_delete(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if request.method == 'POST':
        name = product.name
        product.delete()
        messages.success(request, f'Produto "{name}" excluído.')
        return redirect('product_list')

    return render(request, 'inventory/product_delete.html', {'product': product})


def movement_create(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if request.method == 'POST':
        movement_type = request.POST['tipo']
        quantity = int(request.POST['quantidade'])
        reason = request.POST.get('motivo', '')
        user = request.user if request.user.is_authenticated else None

        try:
            register_movement_service(
                product_id=product.id,
                movement_type=movement_type,
                quantity=quantity,
                reason=reason,
                user=user,
            )
        except InsufficientStockError as error:
            messages.error(
                request,
                f'Quantidade de saída maior que o estoque disponível '
                f'({error.available_quantity} unidades).'
            )
            return redirect('product_detail', product_id=product.id)

        messages.success(request, 'Movimentação registrada.')
        return redirect('product_detail', product_id=product.id)

    return render(request, 'inventory/movement_create.html', {'product': product})
