"""Formularios para los reportes de prueba y su seguimiento."""
from django import forms
from .models import SupportReport


class SupportReportForm(forms.Form):
    category = forms.ChoiceField(
        choices=[('', 'Seleccionar categoría'), *SupportReport.Category.choices], label='Tipo de problema',
    )
    description = forms.CharField(
        label='Descripción breve', max_length=360, widget=forms.Textarea(attrs={'rows': 4}),
        help_text='Describe qué ocurrió. Usa solo datos ficticios y omite contraseñas, PIN y datos personales.',
    )


class SupportReportFilterForm(forms.Form):
    categoria = forms.ChoiceField(
        choices=[('', 'Todas las categorías'), *SupportReport.Category.choices], required=False, label='Categoría',
    )
    estado = forms.ChoiceField(
        choices=[('', 'Todos los estados'), *SupportReport.Status.choices], required=False, label='Estado',
    )


class SupportReportUpdateForm(forms.Form):
    status = forms.ChoiceField(choices=[
        (SupportReport.Status.REVIEW, SupportReport.Status.REVIEW.label),
        (SupportReport.Status.RESOLVED, SupportReport.Status.RESOLVED.label),
    ])
    response = forms.CharField(required=False, max_length=400)
