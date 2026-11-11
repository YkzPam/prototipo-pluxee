"""Validación en servidor de las funciones adicionales de la demostración."""
import uuid
from django import forms
from .models import Merchant, Payment
from .parameters import current as current_parameters
from .validators import reject_dangerous_characters


class MerchantSearchForm(forms.Form):
    q = forms.RegexField(r"^[\w .-]*$", required=False, max_length=60, label='Buscar comercio',
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


class DynamicCodeForm(forms.Form):
    pin = forms.RegexField(r'^[0-9]{4}$', min_length=4, max_length=4, strip=False,
        label='PIN de demostración',
        widget=forms.PasswordInput(attrs={'inputmode': 'numeric', 'autocomplete': 'off', 'maxlength': 4}),
        error_messages={'invalid': 'El PIN de demostración debe contener cuatro dígitos.'})


class PaymentForm(DynamicCodeForm):
    method = forms.ChoiceField(choices=Payment.Method.choices, required=False, widget=forms.HiddenInput)
    merchant = forms.ModelChoiceField(queryset=Merchant.objects.none(), label='Comercio',
        empty_label='Seleccionar comercio')
    amount = forms.IntegerField(min_value=1, max_value=1000000, label='Monto en pesos',
        widget=forms.NumberInput(attrs={'min': 1, 'max': 1000000, 'step': 1, 'inputmode': 'numeric'}))
    qr_code = forms.CharField(max_length=12, required=False, label='Código del comercio',
        validators=[reject_dangerous_characters],
        widget=forms.TextInput(attrs={'autocomplete': 'off', 'autocapitalize': 'characters', 'spellcheck': 'false',
                                     'list': 'qr-commerce-options', 'aria-describedby': 'qr-code-hint'}),
        error_messages={'required': 'Ingresa el código QR del comercio.'})
    dynamic_code = forms.RegexField(r'^[0-9]{4}$', min_length=4, max_length=4, strip=False, required=False,
        label='Clave dinámica',
        widget=forms.PasswordInput(attrs={'inputmode': 'numeric', 'autocomplete': 'off', 'maxlength': 4}),
        error_messages={'invalid': 'La clave dinámica debe contener cuatro dígitos.'})
    idempotency_key = forms.UUIDField(initial=uuid.uuid4, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        method = self.data.get(self.add_prefix('method')) if self.is_bound else self.initial.get('method')
        is_qr = method == Payment.Method.QR
        self.fields['merchant'].queryset = Merchant.objects.filter(active=True)
        self.fields['merchant'].required = not is_qr
        self.fields['qr_code'].required = is_qr
        self.fields['pin'].required = False
        self.max_amount = current_parameters().payment_max_amount
        self.fields['amount'].widget.attrs['max'] = self.max_amount

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount > self.max_amount:
            raise forms.ValidationError(
                f'El monto máximo por compra es ${self.max_amount:,}.'.replace(',', '.'), code='max_amount')
        return amount

    def clean_method(self):
        return self.cleaned_data['method'] or Payment.Method.ONLINE

    def clean(self):
        values = super().clean()
        method = values.get('method')
        if method == Payment.Method.DYNAMIC:
            if values.get('dynamic_code') == '':
                self.add_error('dynamic_code', 'Ingresa la clave dinámica.')
        elif method and values.get('pin') == '':
            self.add_error('pin', 'Ingresa el PIN de demostración.')
        if method == Payment.Method.QR and 'qr_code' in values and 'merchant' in values:
            code, merchant = values['qr_code'], values['merchant']
            if merchant and code.upper() != merchant.code.upper():
                self.add_error('qr_code', 'El código QR no corresponde al comercio seleccionado.')
            elif merchant is None:
                matches = list(self.fields['merchant'].queryset.filter(code__iexact=code)[:2])
                if len(matches) == 1:
                    values['merchant'] = matches[0]
                else:
                    self.add_error('qr_code', 'El código ingresado no identifica a un comercio activo.')
        return values


class ProfileForm(forms.Form):
    first_name = forms.CharField(max_length=40, label='Nombre', widget=forms.TextInput(attrs={'autocomplete': 'off'}))
    last_name = forms.CharField(max_length=40, label='Apellido', widget=forms.TextInput(attrs={'autocomplete': 'off'}))

    @staticmethod
    def _name(value):
        if not value or not any(char.isalpha() for char in value) or any(
                not (char.isalpha() or char in ' -') for char in value):
            raise forms.ValidationError('Este campo solo admite letras, espacios y guiones.')
        return ' '.join(value.split())

    def clean_first_name(self):
        return self._name(self.cleaned_data['first_name'])

    def clean_last_name(self):
        return self._name(self.cleaned_data['last_name'])


class CardActionForm(forms.Form):
    action = forms.ChoiceField(choices=[('block', 'Bloquear tarjeta'), ('unblock', 'Activar tarjeta')])
