from django import forms


class LoginForm(forms.Form):
    username = forms.RegexField(
        r'^[A-Za-z0-9_.@+-]{3,150}$', max_length=150, label='Usuario de prueba',
        error_messages={'invalid': 'El usuario debe tener entre 3 y 150 caracteres válidos.'},
        widget=forms.TextInput(attrs={'autocomplete': 'username', 'autocapitalize': 'none', 'spellcheck': 'false'}),
    )
    password = forms.CharField(max_length=128, strip=False, label='Contraseña',
                               widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}))


class MovementFilterForm(forms.Form):
    desde = forms.DateField(required=False, input_formats=['%Y-%m-%d'])
    hasta = forms.DateField(required=False, input_formats=['%Y-%m-%d'])
    tipo = forms.ChoiceField(required=False, choices=[('todos', 'Todos'), ('cargo', 'Compras'), ('abono', 'Abonos')])
    page = forms.IntegerField(required=False, min_value=1, max_value=100000)

    def clean(self):
        data = super().clean()
        if data.get('desde') and data.get('hasta') and data['desde'] > data['hasta']:
            raise forms.ValidationError('La fecha inicial debe ser anterior o igual a la fecha final.')
        return data


class ServiceStateForm(forms.Form):
    service = forms.ChoiceField(choices=[('balance', 'Saldo'), ('movements', 'Movimientos')])
    state = forms.ChoiceField(choices=[('available', 'Disponible'), ('unavailable', 'Interrumpido')])
