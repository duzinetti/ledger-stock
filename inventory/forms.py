"""
Forms for the inventory app.

Server-side validation (PRD §6.1, §6.2, §8) - relying only on
client-side <input> attributes (min, step, required) doesn't stop a
raw POST request, and the PRD explicitly requires invalid input to
produce a clear server-side error, not a crash.
"""
from django import forms

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

    def clean_price(self):
        price = self.cleaned_data['price']
        if price <= 0:
            raise forms.ValidationError('O preço deve ser maior que zero.')
        return price


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

    type = forms.ChoiceField(choices=TYPE_CHOICES, label='Tipo')
    quantity = forms.IntegerField(min_value=1, label='Quantidade')
    reason = forms.CharField(max_length=200, required=False, label='Motivo')
