"""
Forms for the inventory app.

Server-side validation (PRD §6.1, §6.2, §8) - relying only on
client-side <input> attributes (min, step, required) doesn't stop a
raw POST request, and the PRD explicitly requires invalid input to
produce a clear server-side error, not a crash.
"""
from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth.models import User

from .models import (
    MovementType, 
    Product,
    Category)


class ProductForm(forms.ModelForm):
    """Validates product creation/edit data.

    clean_price enforces PRD §6.1 ("Preço deve ser > 0, validação de
    servidor"); ModelForm already handles required-field and type
    validation for the rest, replacing the raw request.POST[...]
    access that previously let a missing/malformed field crash the
    view with an unhandled 500.
    """

    class Meta:
        model = Product
        fields = ['name', 'category', 'price', 'minimum_quantity']
        labels = {
            'name': 'Nome',
            'category': 'Categoria',
            'price': 'Preço',
            'minimum_quantity': 'Quantidade mínima',
        }
        help_texts = {
            'category': 'Não achou a categoria? Cadastre uma nova na tela de Categorias.',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'minimum_quantity': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].required = False
        if company is not None:
            self.fields['category'].queryset = Category.objects.filter(company=company).order_by('name')


    def clean_price(self):
        price = self.cleaned_data['price']
        if price <= 0:
            raise forms.ValidationError('O preço deve ser maior que zero.')
        return price


class ProductCreateForm(ProductForm):
    """ProductForm + um campo opcional de quantidade inicial em estoque.

    Uma subclasse em vez de adicionar o campo direto no ProductForm
    porque product_update reutiliza ProductForm - se o campo estivesse
    lá, apareceria (vazio, sem sentido) também na tela de edição.
    initial_quantity não é um campo do model Product (vira um
    StockMovement, criado pela view depois que o produto é salvo) -
    por isso é um campo solto do form, não algo declarado em Meta.fields.
    """

    initial_quantity = forms.IntegerField(
        required=False,
        min_value=0,
        initial=0,
        label='Quantidade inicial em estoque',
        help_text='Deixe em branco se o produto ainda não tem estoque.',
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
    )


class MovementForm(forms.Form):
    """Validates a stock movement before it reaches the service layer.

    Kept separate from services.register_movement on purpose: this
    form only checks shape (positive integer quantity, valid type)
    while the service still owns the insufficient-stock check, which
    needs the DB row lock to stay race-free (PRD §6.2/§8) - form
    validation can't do that check itself without reintroducing the
    same concurrency bug the service exists to prevent.
    """

    TYPE_CHOICES = MovementType.choices

    type = forms.ChoiceField(
        choices=TYPE_CHOICES, label='Tipo', widget=forms.Select(attrs={'class': 'form-select'})
    )
    quantity = forms.IntegerField(
        min_value=1, label='Quantidade', widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    reason = forms.CharField(
        max_length=200, required=False, label='Motivo',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    is_sale = forms.BooleanField(
        required=False, initial=True, label='Foi uma venda?',
        help_text='Desmarque se essa saída não for uma venda (perda, ajuste, devolução). '
                   'Não se aplica a entradas.',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )


class EmployeeCreateForm(forms.Form):
    """Cadastro de funcionário pelo Gestor - não é ModelForm porque não
    edita um objeto só (vira User + Group + Membership na service
    layer); só valida forma e unicidade do username aqui.
    """

    ROLE_CHOICES = [('Gestor', 'Gestor'), ('Operador', 'Operador')]

    username = forms.CharField(
        max_length=150, label='Usuário',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    role = forms.ChoiceField(
        choices=ROLE_CHOICES, label='Papel',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Já existe um usuário com esse nome.')
        return username


class StyledPasswordChangeForm(PasswordChangeForm):
    """Mesma ideia do StyledAuthenticationForm logo abaixo:
    PasswordChangeForm é do Django, não dá pra setar widgets via Meta -
    subclassamos só pra injetar classes Bootstrap nos três campos
    (senha atual, nova senha, confirmar nova senha).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


class StyledAuthenticationForm(AuthenticationForm):
    """AuthenticationForm is Django's own class (login.html), not ours -
    can't add widgets= to its Meta like the forms above. Subclassing
    just to inject Bootstrap classes on its two fields.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs['class'] = 'form-control'
        self.fields['password'].widget.attrs['class'] = 'form-control'


class CategoryForm(forms.ModelForm):
    """company não é um campo do formulário (a view atribui na hora de
    salvar, igual product_create faz com Product) - mas o clean_name
    precisa saber a empresa pra checar duplicidade, senão o erro só
    aparece feio, direto do banco, na hora do save().
    """

    class Meta:
        model = Category
        fields = ['name']
        labels = {'name': 'Nome'}
        widgets = {'name': forms.TextInput(attrs={'class': 'form-control'})}

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company

    def clean_name(self):
        name = self.cleaned_data['name']
        if self.company is not None and Category.objects.filter(company=self.company, name__iexact=name).exists():
            raise forms.ValidationError('Já existe uma categoria com esse nome.')
        return name
