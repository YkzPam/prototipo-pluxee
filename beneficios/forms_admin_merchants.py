from django import forms
from django.core.exceptions import ValidationError

from .models import Merchant, MerchantCategory
from .validators import reject_dangerous_characters


class MerchantFilterForm(forms.Form):
    q = forms.CharField(required=False, max_length=80, label='Nombre, código o comuna',
                        validators=[reject_dangerous_characters])
    estado = forms.ChoiceField(required=False, label='Estado', choices=[
        ('', 'Todos'), ('active', 'Activos'), ('inactive', 'Desactivados'),
    ])


class MerchantForm(forms.ModelForm):
    code = forms.RegexField(
        r'^[A-Za-z0-9_-]{3,12}$', max_length=12, label='Código del comercio',
        error_messages={'invalid': 'Usa de 3 a 12 letras sin tilde, números, guion o guion bajo.'},
        widget=forms.TextInput(attrs={'autocomplete': 'off', 'autocapitalize': 'characters'}),
    )

    class Meta:
        model = Merchant
        fields = ['code', 'name', 'category', 'commune', 'address', 'description']
        labels = {
            'name': 'Nombre del comercio', 'category': 'Categoría', 'commune': 'Comuna',
            'address': 'Dirección', 'description': 'Descripción',
        }
        widgets = {
            'name': forms.TextInput(attrs={'autocomplete': 'off'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('name', 'commune', 'address', 'description'):
            self.fields[name].validators.append(reject_dangerous_characters)
        # Las categorías disponibles se administran en la tabla MerchantCategory, no en el código.
        categories = list(MerchantCategory.objects.filter(active=True).values_list('name', flat=True))
        if self.instance.pk and self.instance.category not in categories:
            categories.append(self.instance.category)
        self.fields['category'] = forms.ChoiceField(
            label='Categoría', choices=[('', 'Seleccionar categoría')] + [(value, value) for value in categories],
        )
        self.fields['code'].disabled = bool(self.instance.pk)
        self.fields['code'].help_text = (
            'El código identifica el comercio y se conserva después del alta.'
            if self.instance.pk else 'El código será utilizado para identificar el comercio y los pagos con QR.'
        )

    def clean_code(self):
        code = self.instance.code if self.instance.pk else self.cleaned_data['code'].upper()
        matches = Merchant.objects.filter(code__iexact=code)
        if self.instance.pk:
            matches = matches.exclude(pk=self.instance.pk)
        if matches.exists():
            raise ValidationError('Ese código ya corresponde a otro comercio.')
        return code

    def clean(self):
        values = super().clean()
        for name in ('name', 'commune', 'address', 'description'):
            if name in values:
                values[name] = ' '.join(values[name].split())
        return values


class MerchantStateForm(forms.Form):
    state = forms.ChoiceField(choices=[('active', 'Activar'), ('inactive', 'Desactivar')], widget=forms.HiddenInput)
