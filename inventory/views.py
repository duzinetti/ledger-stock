from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .forms import MovementForm, ProductForm
from .models import (
    Product, 
    StockMovement,
    Membership)
from .services import register_movement as register_movement_service
from .services import (
    InsufficientStockError, 
    InactiveProductError,
    InvalidQuantityError,
    InvalidMovementTypeError
)
from .decorators import gestor_required


@login_required
def product_list(request):
    """Lists products with search and pagination.

    Requires login (PRD §6.4, extended to the listing itself per
    product-owner decision - there is no business reason for stock
    data to be publicly visible).
    """
    search_term = request.GET.get('q', '')

    # with_current_quantity() brings the calculated quantity in a
    # SINGLE query, instead of firing an aggregation query per
    # product (N+1) as would happen using the `current_quantity`
    # property inside the template loop.
    products = Product.objects.active().with_current_quantity().filter(
        company=request.user.membership.company
    ).order_by('name')
    if search_term:
        products = products.filter(name__icontains=search_term)

    paginator = Paginator(products, 10)
    paginated_products = paginator.get_page(request.GET.get('page'))

    return render(request, 'inventory/product_list.html', {
        'products': paginated_products,
        'search_term': search_term,
    })


@login_required
def product_create(request):
    """Creates a product using ProductForm for server-side validation.

    Login-gated per PRD §6.4 (write action).
    """
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save(commit=False)
            product.company = request.user.membership.company
            product.save()
            messages.success(request, 'Produto cadastrado com sucesso.')
            return redirect('product_list')
    else:
        form = ProductForm()
    return render(request, 'inventory/product_create.html', {'form': form})


@login_required
def product_update(request, product_id):
    """Edits an existing product using ProductForm for server-side validation.

    Login-gated per PRD §6.4 (write action).
    """
    product = get_object_or_404(Product, id=product_id, company=request.user.membership.company)

    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, 'Produto atualizado.')
            return redirect('product_detail', product_id=product.id)
    else:
        form = ProductForm(instance=product)

    return render(request, 'inventory/product_update.html', {'product': product, 'form': form})


@login_required
def product_detail(request, product_id):
    """Shows one product plus its full movement history.

    Login-gated along with the rest of the app per product-owner
    decision (see product_list docstring).
    """
    product = get_object_or_404(Product, id=product_id, company=request.user.membership.company)
    # select_related('product') avoids N+1 when rendering the
    # history: without it, each listed movement would fire an extra
    # query to fetch the related product (used in __str__ and in the
    # template).
    movements = product.movements.select_related('product').order_by('-date')

    paginator = Paginator(movements, 20)
    paginated_movements = paginator.get_page(request.GET.get('page'))

    return render(request, 'inventory/product_detail.html', {
        'product': product,
        'movements': paginated_movements,
    })


@login_required
@gestor_required
def product_delete(request, product_id):
    """Soft-deletes a product (confirmation page on GET, deactivation on POST).

    Sets active=False instead of removing the row, so the product's
    movement history stays intact for audit purposes - resolves the
    soft-delete open question from PRD §8/§10.2. Login-gated per
    PRD §6.4.
    """
    product = get_object_or_404(Product, id=product_id, company=request.user.membership.company)

    if request.method == 'POST':
        name = product.name
        product.active = False
        product.save(update_fields=['active'])
        messages.success(request, f'Produto "{name}" inativado.')
        return redirect('product_list')

    return render(request, 'inventory/product_delete.html', {'product': product})


@login_required
@gestor_required
def product_inactive_list(request):
    """Lists inactive (soft-deleted) products of the Gestor's company (#29).

    Restricted to the Gestor group - same permission that guards
    product_delete, mirroring the PRD decision that both directions
    of the soft-delete (deactivate/reactivate) require the same role.
    """
    products = Product.objects.filter(
        active=False, company=request.user.membership.company
    ).order_by('name')

    return render(request, 'inventory/product_inactive_list.html', {
        'products': products,
    })


@login_required
@gestor_required
def product_reactivate(request, product_id):
    """Reactivates a soft-deleted product (#29)."""
    product = get_object_or_404(Product, id=product_id, company=request.user.membership.company)

    if request.method == 'POST':
        product.active = True
        product.save(update_fields=['active'])
        messages.success(request, f'Produto "{product.name}" reativado.')
        return redirect('product_inactive_list')

    return render(request, 'inventory/product_reactivate.html', {'product': product})


@login_required
def movement_create(request, product_id):
    """Registers a stock movement (in/out) for one product.

    Login-gated per PRD §6.4. Delegates the actual quantity/locking
    logic to services.register_movement so this view and any future
    API share one source of truth for the concurrency-safety rule.
    """
    product = get_object_or_404(Product, id=product_id, company=request.user.membership.company)

    if request.method == 'POST':
        form = MovementForm(request.POST)
        if form.is_valid():
            try:
                register_movement_service(
                    product_id=product.id,
                    movement_type=form.cleaned_data['type'],
                    quantity=form.cleaned_data['quantity'],
                    reason=form.cleaned_data['reason'],
                    user=request.user,
                )
            except InsufficientStockError as error:
                messages.error(
                    request,
                    f'Quantidade de saída maior que o estoque disponível '
                    f'({error.available_quantity} unidades).'
                )
                return redirect('product_detail', product_id=product.id)
            except InactiveProductError:
                messages.error(
                    request,
                    'Produto inativo e sem estoque - não é possível registrar movimentação.'
                )
                return redirect('product_detail', product_id=product.id)
            except Product.DoesNotExist:
                messages.error(
                    request,
                    'Este produto não existe mais - não foi possível registrar a movimentação.'
                )
                return redirect('product_list')
            except InvalidQuantityError:
                messages.error(
                    request,
                    'Quantidade inválida - deve ser um número inteiro maior que zero.'
                )
                return redirect('product_detail', product_id=product.id)
            except InvalidMovementTypeError:
                messages.error(
                    request,
                    'Tipo de movimentação inválido.'
                )
                return redirect('product_detail', product_id=product.id)

            messages.success(request, 'Movimentação registrada.')
            return redirect('product_detail', product_id=product.id)
    else:
        form = MovementForm()

    return render(request, 'inventory/movement_create.html', {'product': product, 'form': form})


@login_required
@gestor_required
def employee_list(request):
    """Lists the employees (Membership) of the logged-in Gestor's company.

    Restricted to the Gestor group (#47) - Operador shouldn't see or
    manage other employees' access.
    """
    memberships = Membership.objects.filter(
        company=request.user.membership.company
    ).select_related('user').order_by('user__username')

    return render(request, 'inventory/employee_list.html', {
        'memberships': memberships
    })


@login_required
@gestor_required
def employee_toggle_active(request, membership_id):
    """Activates/deactivates an employee's login access (#47).

    Toggles User.is_active instead of deleting the User - StockMovement.user
    has on_delete=SET_NULL, so deleting the account would erase the
    authorship of movements they registered, weakening the auditable
    history (PRD §3). Same reasoning already applied to Product's
    soft delete.
    """
    membership = get_object_or_404(
        Membership, id=membership_id, company=request.user.membership.company
    )

    if membership.user_id == request.user.id:
        messages.error(request, 'Você não pode desativar seu próprio acesso.')
        return redirect('employee_list')

    if request.method == 'POST':
        membership.user.is_active = not membership.user.is_active
        membership.user.save(update_fields=['is_active'])
        status = 'ativado' if membership.user.is_active else 'desativado'
        messages.success(request, f'Acesso de {membership.user.username} {status}.')
        return redirect('employee_list')

    return render(request, 'inventory/employee_toggle_active.html', {'membership': membership})
