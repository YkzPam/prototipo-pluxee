import uuid

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import (
    MinimumLengthValidator, get_default_password_validators, password_validators_help_texts, validate_password,
)
from django.core.exceptions import ValidationError

from .forms import LoginForm
from .forms_extra import DynamicCodeForm, ProfileForm
from .validators import reject_dangerous_characters


class PasswordFields(forms.Form):
    password1 = forms.CharField(
        label='Contraseña nueva', max_length=128, strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )
    password2 = forms.CharField(
        label='Confirmar contraseña', max_length=128, strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['password1'].help_text = ' '.join(password_validators_help_texts())

    def password_user(self, values):
        return self.user

    def clean(self):
        values = super().clean()
        password1, password2 = values.get('password1'), values.get('password2')
        if password1 and password2 and password1 != password2:
            self.add_error('password2', 'Las contraseñas deben coincidir.')
        if password1:
            try:
                validate_password(password1, self.password_user(values))
            except ValidationError as error:
                self.add_error('password1', error)
        return values


class RegistrationForm(PasswordFields, ProfileForm):
    username = LoginForm.base_fields['username']
    pin = DynamicCodeForm.base_fields['pin']
    field_order = ['username', 'first_name', 'last_name', 'password1', 'password2', 'pin']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.minimum_password_length = max(
            (validator.min_length for validator in get_default_password_validators()
             if isinstance(validator, MinimumLengthValidator)), default=0,
        )
        self.fields['username'].label = 'Usuario'
        self.fields['username'].help_text = 'Usa letras sin tilde, números o los signos . _ @ -.'
        self.fields['password1'].label = 'Contraseña'
        self.fields['password1'].help_text = 'Evita contraseñas comunes o parecidas a tus datos.'
        self.fields['pin'].label = 'PIN de compra'
        self.fields['pin'].help_text = 'Elige cuatro dígitos para autorizar compras.'
        self.fields['pin'].error_messages['invalid'] = 'El PIN debe tener cuatro dígitos.'

    def clean_username(self):
        username = self.cleaned_data['username'].lower()
        if get_user_model().objects.filter(username__iexact=username).exists():
            raise ValidationError('Ese nombre de usuario no está disponible.')
        return username

    def password_user(self, values):
        fields = ('username', 'first_name', 'last_name')
        return get_user_model()(**{field: values.get(field, '') for field in fields})


class AccountFilterForm(forms.Form):
    q = forms.CharField(required=False, max_length=150, label='Buscar por usuario',
                        validators=[reject_dangerous_characters])
    estado = forms.ChoiceField(required=False, label='Estado', choices=[
        ('', 'Todos'), ('active', 'Activas'), ('inactive', 'Desactivadas'),
    ])


class AccountStateForm(forms.Form):
    state = forms.ChoiceField(choices=[('active', 'Activar'), ('inactive', 'Desactivar')], widget=forms.HiddenInput)


class CreditForm(forms.Form):
    amount = forms.IntegerField(min_value=1, max_value=1000000, label='Monto del abono en pesos',
                                widget=forms.NumberInput(attrs={'inputmode': 'numeric'}))
    reference = forms.UUIDField(initial=uuid.uuid4, widget=forms.HiddenInput)


class AccountCardForm(forms.Form):
    state = forms.ChoiceField(choices=[('block', 'Bloquear'), ('unblock', 'Activar')], widget=forms.HiddenInput)
