"""Registro del cambio y del estado del reporte en una única transacción."""
from .models import SupportReportUpdate


def capture_report(report):
    return {
        'status': report.status, 'priority': report.priority,
        'assigned_to_id': report.assigned_to_id, 'response': report.response,
    }


def save_report_change(report, previous, actor, *, update_fields):
    current = capture_report(report)
    if current == previous:
        return False
    report.save(update_fields=[*update_fields, 'updated_at'])
    SupportReportUpdate.objects.create(
        report=report, actor=actor, old_status=previous['status'], new_status=current['status'],
        old_priority=previous['priority'], new_priority=current['priority'],
        old_assigned_to_id=previous['assigned_to_id'], new_assigned_to_id=current['assigned_to_id'],
        response_changed=previous['response'] != current['response'], response=current['response'],
    )
    return True
