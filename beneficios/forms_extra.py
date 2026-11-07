"""Validación en servidor de las funciones adicionales de la demostración."""
import uuid
from django import forms
from .models import Merchant


class MerchantSearchForm(forms.Form):
    q = forms.RegexField(r"^[\w .'-]*$", required=False, max_length=60, label='Buscar comercio',
        error_messages={'invalid': 'La búsqueda admite letras, números, espacios y guiones.'})
    categoria = forms.ChoiceField(required=False, label='Categoría')
    comuna = forms.ChoiceField(required=False, label='Comuna')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        active = Merchant.objects.filter(active=True)
        self.fields['categoria'].choices = [('', 'Todas las categorías')] + [
            (value, value) for value in active.order_by('category').values_list('category', flat=True).distinct()]
        self.fields['comuna'].choices = [('', 'Todas las comunas')] + [
            (value, value) for value in active.order_by('commune').values_list('commune', flat=True).distinct()]


class PaymentForm(forms.Form):
    merchant = forms.ModelChoiceField(queryset=Merchant.objects.none(), label='Comercio de prueba', empty_label='Seleccionar comercio')
    amount = forms.IntegerField(min_value=1, max_value=1000000, label='Monto en pesos',
        widget=forms.NumberInput(attrs={'min': 1, 'max': 1000000, 'step': 1, 'inputmode': 'numeric'}))
    pin = forms.RegexField(r'^\d{4}$', min_length=4, max_length=4, strip=False, label='PIN de demostración',
        widget=forms.PasswordInput(attrs={'inputmode': 'numeric', 'autocomplete': 'off', 'maxlength': 4}),
        error_messages={'invalid': 'El PIN de demostración debe contener cuatro dígitos.'})
    idempotency_key = forms.UUIDField(initial=uuid.uuid4, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['merchant'].queryset = Merchant.objects.filter(active=True)


class ProfileForm(forms.Form):
    first_name = forms.CharField(max_length=40, label='Nombre ficticio', widget=forms.TextInput(attrs={'autocomplete': 'off'}))
    last_name = forms.CharField(max_length=40, label='Apellido ficticio', widget=forms.TextInput(attrs={'autocomplete': 'off'}))

    @staticmethod
    def _name(value):
        if not value or not any(char.isalpha() for char in value) or any(
                not (char.isalpha() or char in " '-") for char in value):
            raise forms.ValidationError('El nombre ficticio solo admite letras, espacios, apóstrofes y guiones.')
        return ' '.join(value.split())

    def clean_first_name(self):
        return self._name(self.cleaned_data['first_name'])

    def clean_last_name(self):
        return self._name(self.cleaned_data['last_name'])


class CardActionForm(forms.Form):
    action = forms.ChoiceField(choices=[('block', 'Bloquear tarjeta'), ('unblock', 'Activar tarjeta')])
