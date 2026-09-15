"""Authorized projections of actionable scheduling exceptions."""

from django.utils import timezone

from ros_xolo.core.models import Incidencia
from ros_xolo.core.services.authorization import authorize_planner


def pending_publication_alert(period, has_pending_changes):
    if period.current_publication_id is None:
        return {
            "key": f"initial-publication:{period.id}",
            "type": "initial_publication_pending",
            "priority": "medium",
            "period_id": str(period.id),
            "required_action": "Revisar y publicar el periodo.",
        }
    if has_pending_changes:
        return {
            "key": f"revision:{period.id}",
            "type": "revision_pending",
            "priority": "medium",
            "period_id": str(period.id),
            "required_action": "Revisar las diferencias y publicar.",
        }
    return None


def overlap_alert(error, *, period_id):
    """Project a transient overlap without enriching restricted conflicts."""

    return {
        "key": f"overlap:{period_id}",
        "type": "overlap",
        "priority": "high",
        "period_id": str(period_id),
        "context": {"conflicts": error.conflicts},
        "fields": error.fields,
        "required_action": error.action,
    }


def get_active_alerts(actor, branch_id, *, period_id=None):
    authorize_planner(actor, branch_id)
    incidents = Incidencia.objects.filter(
        organization_id=actor.organization_id,
        branch_id=branch_id,
        type="employee_ineligible_future",
        status="open",
    ).select_related("employee")
    if period_id is not None:
        incidents = incidents.filter(period_id=period_id)
    return [
        {
            "key": f"employee-ineligible:{row.id}",
            "type": "employee_ineligible_future",
            "priority": "high",
            "branch_id": str(row.branch_id),
            "period_id": str(row.period_id),
            "employee_id": str(row.employee_id) if row.employee_id else None,
            "employee_label": row.employee.display_name if row.employee else None,
            "affected_assignment_ids": row.affected_assignment_ids,
            "detected_at": row.occurred_at.isoformat(),
            "required_action": "Retira o reasigna las jornadas futuras antes de republicar.",
            "verified_at": timezone.now().isoformat(),
        }
        for row in incidents.order_by("occurred_at", "id")
    ]
