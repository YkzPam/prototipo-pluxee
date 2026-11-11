from django import forms
from django.contrib.auth import get_user_model

from .models import SupportReport
from .validators import reject_dangerous_characters


class IncidentManagementForm(forms.Form):
    status = forms.ChoiceField(label='Estado')
    priority = forms.ChoiceField(label='Prioridad', choices=SupportReport.Priority.choices)
    assigned_to = forms.ModelChoiceField(label='Responsable', required=False,
        queryset=get_user_model().objects.none(), empty_label='Sin asignar')
    response = forms.CharField(label='Respuesta al beneficiario', max_length=400, required=False,
        widget=forms.Textarea(attrs={'rows': 4}), validators=[reject_dangerous_characters])

    def __init__(self, *args, report, **kwargs):
        from .views_support import NEXT_STATUS

        super().__init__(*args, **kwargs)
        permitted = [report.status]
        if report.status in NEXT_STATUS:
            permitted.append(NEXT_STATUS[report.status])
        self.fields['status'].choices = [(value, label) for value, label in SupportReport.Status.choices
                                         if value in permitted]
        self.fields['assigned_to'].queryset = get_user_model().objects.filter(
            is_staff=True, is_active=True,
        ).order_by('username')
