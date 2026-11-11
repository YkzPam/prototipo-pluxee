from datetime import date

from django import forms

from .validators import reject_dangerous_characters


class MovementReportForm(forms.Form):
    desde = forms.DateField(label='Desde', input_formats=['%Y-%m-%d'],
                            widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))
    hasta = forms.DateField(label='Hasta', input_formats=['%Y-%m-%d'],
                            widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))
    tipo = forms.ChoiceField(required=False, label='Tipo de movimiento', choices=[
        ('', 'Todos'), ('abono', 'Abonos'), ('cargo', 'Compras'),
    ])
    usuario = forms.CharField(required=False, max_length=150, label='Usuario exacto',
                              widget=forms.TextInput(attrs={'autocomplete': 'off'}),
                              validators=[reject_dangerous_characters])

    def clean(self):
        values = super().clean()
        first, last = values.get('desde'), values.get('hasta')
        if first and last:
            if first > last:
                raise forms.ValidationError('La fecha inicial debe ser anterior o igual a la fecha final.')
            if (last - first).days + 1 > 366:
                raise forms.ValidationError('El periodo puede abarcar hasta 366 días. Acota las fechas para continuar.')
            if last == date.max:
                self.add_error('hasta', 'Selecciona una fecha final anterior al 31 de diciembre de 9999.')
        return values
