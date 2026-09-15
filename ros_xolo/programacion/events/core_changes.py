"""Translate eligibility changes into durable scheduling incidents."""

from collections import defaultdict

from django.utils import timezone

from ros_xolo.core.events.registry import register
from ros_xolo.core.models import Empleado, HabilitacionSucursal, Incidencia
from ros_xolo.programacion.models import JornadaPublicada, PeriodoProgramacion


def _eligible(organization_id, branch_id, employee_id):
    return Empleado.objects.filter(
        pk=employee_id, organization_id=organization_id, active=True
    ).exists() and HabilitacionSucursal.objects.filter(
        organization_id=organization_id,
        branch_id=branch_id,
        employee_id=employee_id,
        enabled=True,
    ).exists()


def handle_eligibility_change(event):
    validation_time = event.occurred_at or timezone.now()
    periods = PeriodoProgramacion.objects.filter(
        organization_id=event.organization_id,
        current_publication_id__isnull=False,
    )
    if event.branch_id:
        periods = periods.filter(branch_id=event.branch_id)
    publication_ids = dict(periods.values_list("current_publication_id", "id"))
    rows = JornadaPublicada.objects.filter(
        organization_id=event.organization_id,
        publication_id__in=publication_ids,
        starts_at__gt=validation_time,
    )
    employee_id = event.payload.get("employee_id") if isinstance(event.payload, dict) else None
    if employee_id:
        rows = rows.filter(employee_id=employee_id)

    affected = defaultdict(list)
    for row in rows:
        if not _eligible(event.organization_id, row.branch_id, row.employee_id):
            affected[(publication_ids[row.publication_id], row.branch_id, row.employee_id)].append(
                str(row.assignment_id)
            )

    active_keys = set(affected)
    for (period_id, branch_id, row_employee_id), assignment_ids in affected.items():
        incident = Incidencia.objects.filter(
            organization_id=event.organization_id,
            branch_id=branch_id,
            employee_id=row_employee_id,
            period_id=period_id,
            type="employee_ineligible_future",
            status="open",
        ).first()
        if incident:
            incident.affected_assignment_ids = sorted(set(assignment_ids))
            incident.save(update_fields=["affected_assignment_ids"])
        else:
            Incidencia.objects.create(
                organization_id=event.organization_id,
                branch_id=branch_id,
                employee_id=row_employee_id,
                period_id=period_id,
                type="employee_ineligible_future",
                affected_assignment_ids=sorted(set(assignment_ids)),
                source_event=event,
                actor_id=event.actor_id,
                correlation_id=event.correlation_id,
            )

    open_incidents = Incidencia.objects.filter(
        organization_id=event.organization_id,
        type="employee_ineligible_future",
        status="open",
    )
    if event.branch_id:
        open_incidents = open_incidents.filter(branch_id=event.branch_id)
    if employee_id:
        open_incidents = open_incidents.filter(employee_id=employee_id)
    for incident in open_incidents:
        key = (incident.period_id, incident.branch_id, incident.employee_id)
        if key not in active_keys and _eligible(
            event.organization_id, incident.branch_id, incident.employee_id
        ):
            incident.status = "resolved"
            incident.resolved_at = validation_time
            incident.resolution_event = event
            incident.save(update_fields=["status", "resolved_at", "resolution_event"])


def resolve_incidents_after_publication(period, publication_event):
    for incident in Incidencia.objects.filter(
        organization_id=period.organization_id,
        branch_id=period.branch_id,
        period_id=period.id,
        type="employee_ineligible_future",
        status="open",
    ):
        future_ids = set(
            str(value)
            for value in period.draft.assignments.filter(
                starts_at__gt=publication_event.occurred_at,
                employee_id=incident.employee_id,
            ).values_list("assignment_id", flat=True)
        )
        if not future_ids.intersection(incident.affected_assignment_ids):
            incident.status = "resolved"
            incident.resolved_at = publication_event.occurred_at
            incident.resolution_event = publication_event
            incident.save(update_fields=["status", "resolved_at", "resolution_event"])


register("core.membership_changed", handle_eligibility_change)
register("core.catalog_changed", handle_eligibility_change)
