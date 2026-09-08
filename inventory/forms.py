"""
Forms for the inventory app.

Server-side validation (PRD §6.1, §6.2, §8) - relying only on
client-side <input> attributes (min, step, required) doesn't stop a
raw POST request, and the PRD explicitly requires invalid input to
produce a clear server-side error, not a crash.
"""
from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import MovementType, Product


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
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.TextInput(attrs={'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'minimum_quantity': forms.NumberInput(attrs={'class': 'form-control'}),
        }

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


class StyledAuthenticationForm(AuthenticationForm):
    """AuthenticationForm is Django's own class (login.html), not ours -
    can't add widgets= to its Meta like the forms above. Subclassing
    just to inject Bootstrap classes on its two fields.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs['class'] = 'form-control'
        self.fields['password'].widget.attrs['class'] = 'form-control'
