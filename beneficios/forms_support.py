"""Formularios para los reportes de prueba y su seguimiento."""
from django import forms
from django.contrib.auth import get_user_model
from .models import SupportReport
from .validators import reject_dangerous_characters


class SupportReportForm(forms.Form):
    category = forms.ChoiceField(
        choices=[('', 'Seleccionar categoría'), *SupportReport.Category.choices], label='Tipo de problema',
    )
    description = forms.CharField(
        label='Descripción breve', max_length=360, widget=forms.Textarea(attrs={'rows': 4}),
        validators=[reject_dangerous_characters],
        help_text='Describe qué ocurrió. Usa datos de ejemplo y omite contraseñas, PIN y datos personales.',
    )


class SupportReportFilterForm(forms.Form):
    categoria = forms.ChoiceField(
        choices=[('', 'Todas las categorías'), *SupportReport.Category.choices], required=False, label='Categoría',
    )
    estado = forms.ChoiceField(
        choices=[('', 'Todos los estados'), *SupportReport.Status.choices], required=False, label='Estado',
    )
    prioridad = forms.ChoiceField(
        choices=[('', 'Todas las prioridades'), *SupportReport.Priority.choices], required=False, label='Prioridad',
    )
    responsable = forms.ChoiceField(required=False, label='Responsable')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['responsable'].choices = [('', 'Todos'), ('none', 'Sin asignar')] + [
            (str(pk), username) for pk, username in get_user_model().objects.filter(
                is_staff=True, is_active=True,
            ).order_by('username').values_list('pk', 'username')
        ]


class SupportReportUpdateForm(forms.Form):
    status = forms.ChoiceField(choices=[
        (SupportReport.Status.REVIEW, SupportReport.Status.REVIEW.label),
        (SupportReport.Status.RESOLVED, SupportReport.Status.RESOLVED.label),
    ])
    response = forms.CharField(required=False, max_length=400, validators=[reject_dangerous_characters])
