from datetime import timedelta

from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import (
    Q,
    Sum,
    F,
    DecimalField,
)
from django.db.models.functions import TruncDate
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse
from django.utils import timezone
from .forms import EmployeeCreateForm, MovementForm, ProductCreateForm, ProductForm, StyledPasswordChangeForm
from .models import (
    MovementType,
    Product,
    StockMovement,
    Membership)
from .services import register_movement as register_movement_service
from .services import create_employee, reset_employee_password
from .services import (
    InsufficientStockError,
    InactiveProductError,
    InvalidQuantityError,
    InvalidMovementTypeError
)
from .decorators import gestor_required


def robots_txt(request):
    """Bloqueia indexação por robôs de busca - o app inteiro fica atrás
    de login (nenhuma página é realmente pública), mas isso é defesa em
    profundidade: não custa nada garantir que um buscador nunca tente
    listar "/produtos/" ou dados de uma empresa cliente.
    """
    return HttpResponse('User-agent: *\nDisallow: /\n', content_type='text/plain')


def privacy_policy(request):
    """Política de privacidade - única página do app que não exige
    login, de propósito: alguém precisa poder ler isso antes de decidir
    usar o sistema, não só depois de já ter uma conta.
    """
    return render(request, 'inventory/privacy_policy.html')


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
        # Sempre busca por nome; se o termo digitado for só dígitos,
        # também aceita ele como ID exato (ex.: "12" bate o produto de
        # nome "12 Pilhas AA" OU o produto de ID 12).
        query = Q(name__icontains=search_term)
        if search_term.isdigit():
            query |= Q(id=search_term)
        products = products.filter(query)

    paginator = Paginator(products, 10)
    paginated_products = paginator.get_page(request.GET.get('page'))

    return render(request, 'inventory/product_list.html', {
        'products': paginated_products,
        'search_term': search_term,
    })


@login_required
def product_create(request):
    """Creates a product using ProductCreateForm for server-side validation.

    Login-gated per PRD §6.4 (write action). Uses ProductCreateForm (not
    ProductForm) because creation optionally accepts an initial stock
    quantity - a field that only makes sense once, at creation time, so
    it lives in a subclass instead of the shared ProductForm used by
    product_update too.
    """
    if request.method == 'POST':
        form = ProductCreateForm(request.POST)
        if form.is_valid():
            # transaction.atomic() aqui garante que produto + movimento
            # inicial nascem juntos: se o registro do movimento falhar
            # por algum motivo, o produto também não fica salvo "no
            # vácuo" com uma quantidade inicial que o usuário pediu mas
            # nunca foi de fato registrada.
            with transaction.atomic():
                product = form.save(commit=False)
                product.company = request.user.membership.company
                product.save()

                initial_quantity = form.cleaned_data.get('initial_quantity')
                if initial_quantity:
                    register_movement_service(
                        product_id=product.id,
                        movement_type=MovementType.IN,
                        quantity=initial_quantity,
                        reason='Estoque inicial',
                        user=request.user,
                    )
            messages.success(request, 'Produto cadastrado com sucesso.')
            return redirect('product_list')
    else:
        form = ProductCreateForm()
    return render(request, 'inventory/product_create.html', {'form': form})


@login_required
def product_update(request, product_id):
    """Edits an existing product using ProductForm for server-side validation.

    Login-gated per PRD §6.4 (write action). Also renders a second,
    independent MovementForm in the same page - Editar passou a
    concentrar as ações de escrita sobre o produto (dados + estoque),
    enquanto Ver ficou só leitura. Os dois forms postam pra views
    diferentes (este e movement_create); não foram fundidos num só
    porque validam coisas diferentes - editar produto é um ModelForm
    simples, registrar movimento passa pelo service com
    select_for_update().
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

    return render(request, 'inventory/product_update.html', {
        'product': product,
        'form': form,
        'movement_form': MovementForm(),
    })


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

    On a business-rule error (insufficient stock, inactive product...)
    this re-renders product_update.html with the error attached to the
    form via form.add_error(), instead of a message + redirect - that
    way the user sees the error next to the field, on the same page
    where the embedded movement form lives, without losing what they
    typed (Nielsen heuristic #9: errors should appear near the field
    that caused them, not as a banner on a fresh page). The one
    exception is Product.DoesNotExist: there is no page to return the
    user to if the product itself is gone, so that case keeps the
    message + redirect to product_list.
    """
    product = get_object_or_404(Product, id=product_id, company=request.user.membership.company)

    if request.method != 'POST':
        return render(request, 'inventory/movement_create.html', {
            'product': product,
            'form': MovementForm(),
        })

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
            form.add_error(
                'quantity',
                f'Quantidade de saída maior que o estoque disponível '
                f'({error.available_quantity} unidades).'
            )
        except InactiveProductError:
            form.add_error(
                None,
                'Produto inativo e sem estoque - não é possível registrar movimentação.'
            )
        except Product.DoesNotExist:
            messages.error(
                request,
                'Este produto não existe mais - não foi possível registrar a movimentação.'
            )
            return redirect('product_list')
        except InvalidQuantityError:
            form.add_error('quantity', 'Quantidade inválida - deve ser um número inteiro maior que zero.')
        except InvalidMovementTypeError:
            form.add_error('type', 'Tipo de movimentação inválido.')
        else:
            messages.success(request, 'Movimentação registrada.')
            return redirect('product_update', product_id=product.id)

    # form inválido (validação do Django) OU um erro de regra de
    # negócio foi anexado ao form acima - nos dois casos, volta pra
    # product_update.html com o form da movimentação preenchido e com erro.
    return render(request, 'inventory/product_update.html', {
        'product': product,
        'form': ProductForm(instance=product),
        'movement_form': form,
    })


@login_required
def dashboard(request):
    company = request.user.membership.company
    products = Product.objects.active().with_current_quantity().filter(company=company)
    total_value = products.aggregate(
        total=Sum(F('current_qty') * F('price'), output_field=DecimalField(max_digits=12, decimal_places=2))
    )['total'] or 0
    critical_products = products.filter(is_low_stock=True).order_by('current_qty')

    thirty_days_ago = timezone.now() - timedelta(days=30)
    movement_count = StockMovement.objects.filter(
        product__company=company, date__gte=thirty_days_ago
    ).count()
    movements = (
        StockMovement.objects
        .filter(product__company=company, date__gte=thirty_days_ago)
        .annotate(day=TruncDate('date'))
        .values('day', 'type')
        .annotate(total=Sum('quantity'))
        .order_by('day')
    )

    # O gráfico quer 3 listas paralelas (um dia, uma entrada, uma saída
    # por posição) - o passo acima devolve uma linha por combinação de
    # dia+tipo, então primeiro reorganiza isso num dicionário por dia.
    dados_por_dia = {}
    for m in movements:
        dia = m['day'].isoformat()
        dados_por_dia.setdefault(dia, {'entrada': 0, 'saida': 0})
        if m['type'] == MovementType.IN:
            dados_por_dia[dia]['entrada'] = m['total']
        else:
            dados_por_dia[dia]['saida'] = m['total']

    dias = sorted(dados_por_dia.keys())
    entradas = [dados_por_dia[d]['entrada'] for d in dias]
    saidas = [dados_por_dia[d]['saida'] for d in dias]

    return render(request, 'inventory/dashboard.html', {
        'total_value': total_value,
        'critical_products': critical_products,
        'critical_count': critical_products.count(),
        'movement_count': movement_count,
        'chart_labels': dias,
        'chart_entradas': entradas,
        'chart_saidas': saidas,
    })



@login_required
@gestor_required
def employee_list(request):
    """Lists the employees (Membership) of the logged-in Gestor's company.

    Restricted to the Gestor group (#47) - Operador shouldn't see or
    manage other employees' access.
    """
    # prefetch_related('user__groups') traz os grupos (papéis) de todos
    # os funcionários numa única query extra, em vez de uma query de
    # grupo por linha da tabela (N+1) quando o template ler
    # membership.user.groups.all para mostrar Gestor/Operador.
    memberships = Membership.objects.filter(
        company=request.user.membership.company
    ).select_related('user').prefetch_related('user__groups').order_by('user__username')

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


@login_required
@gestor_required
def employee_create(request):
    """Cadastra um funcionário novo (User + Group + Membership) com
    senha temporária gerada pelo sistema.

    Sem redirect no sucesso, de propósito: a senha temporária só existe
    naquele exato momento, em memória - nunca é salva em texto puro em
    lugar nenhum (o banco só guarda o hash). Se desse redirect e
    perdesse o contexto, não teria como mostrar essa senha de novo pro
    Gestor sem resetá-la de novo.
    """
    if request.method == 'POST':
        form = EmployeeCreateForm(request.POST)
        if form.is_valid():
            user, temp_password = create_employee(
                company=request.user.membership.company,
                username=form.cleaned_data['username'],
                role=form.cleaned_data['role'],
            )
            return render(request, 'inventory/employee_create_done.html', {
                'created_user': user,
                'temp_password': temp_password,
            })
    else:
        form = EmployeeCreateForm()

    return render(request, 'inventory/employee_create.html', {'form': form})


@login_required
@gestor_required
def employee_reset_password(request, membership_id):
    """Gera uma nova senha temporária pra um funcionário que esqueceu a
    própria senha (#26 - sem infraestrutura de e-mail, quem resolve
    isso é o Gestor, presencialmente/por WhatsApp).
    """
    membership = get_object_or_404(
        Membership, id=membership_id, company=request.user.membership.company
    )

    if membership.user_id == request.user.id:
        messages.error(request, 'Você não pode redefinir sua própria senha por aqui - use "Trocar senha".')
        return redirect('employee_list')

    if request.method == 'POST':
        temp_password = reset_employee_password(membership)
        return render(request, 'inventory/employee_create_done.html', {
            'created_user': membership.user,
            'temp_password': temp_password,
        })

    return render(request, 'inventory/employee_reset_password.html', {'membership': membership})


class StyledPasswordChangeView(PasswordChangeView):
    """PasswordChangeView pronta do Django, com três ajustes:
    - StyledPasswordChangeForm pra ficar com a cara Bootstrap do resto
      do app (mesmo motivo do StyledAuthenticationForm no login).
    - Zera Membership.must_change_password quando a troca dá certo -
      sem isso, ForcePasswordChangeMiddleware ficaria redirecionando a
      pessoa pra essa mesma tela pra sempre, mesmo já tendo trocado.
    - Desloga e manda pro login em vez de manter a sessão logada
      (comportamento padrão do Django) - decisão do product owner:
      depois de trocar a senha, a pessoa precisa provar que sabe a
      senha nova entrando de novo com ela.
    """
    form_class = StyledPasswordChangeForm

    def form_valid(self, form):
        # super().form_valid() salva a senha nova e chama
        # update_session_auth_hash() pra manter a sessão atual válida -
        # descartamos essa resposta de propósito, porque o passo
        # seguinte (logout) invalida a sessão de qualquer forma.
        super().form_valid(form)
        if hasattr(self.request.user, 'membership'):
            self.request.user.membership.must_change_password = False
            self.request.user.membership.save(update_fields=['must_change_password'])

        logout(self.request)
        messages.success(self.request, 'Senha alterada com sucesso. Faça login novamente.')
        return redirect('login')
