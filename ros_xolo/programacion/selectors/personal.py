"""Privacy-first projection for the authenticated employee's published schedule."""
import hashlib
import json
from django.utils import timezone
from ros_xolo.core.services.authorization import resolve_employee
from ros_xolo.programacion.models import FilaEmpleadoPublicada, JornadaPublicada, PeriodoProgramacion, PublicacionProgramacion


def get_personal_schedule(actor, date_from, date_to):
    employee = resolve_employee(actor)
    periods = PeriodoProgramacion.objects.filter(organization_id=actor.organization_id, date_to__gte=date_from, date_from__lte=date_to).select_related("branch")
    result_periods, assignments = [], []
    for period in periods:
        publication = None
        if period.current_publication_id:
            publication = PublicacionProgramacion.objects.filter(pk=period.current_publication_id, period=period).first()
        rostered = bool(publication and FilaEmpleadoPublicada.objects.filter(publication=publication, employee=employee).exists())
        rows = JornadaPublicada.objects.filter(publication=publication, employee=employee) if publication else JornadaPublicada.objects.none()
        serialized = [{"assignment_id": str(row.assignment_id), "branch_id": str(row.branch_id), "starts_at": row.starts_at.isoformat(), "ends_at": row.ends_at.isoformat(), "labels": row.labels, "role_id": str(row.role_id) if row.role_id else None, "station_id": str(row.station_id) if row.station_id else None, "version": publication.version} for row in rows]
        assignments.extend(serialized)
        result_periods.append({"period_id": str(period.id), "branch_id": str(period.branch_id), "branch_label": period.branch.name, "date_from": period.date_from.isoformat(), "date_to": period.date_to.isoformat(), "publication_state": "published" if publication else "not_published", "assignment_state": "assigned" if serialized else "none", "included_in_roster": rostered, "version": publication.version if publication else None})
    material = {"employee_id": str(employee.id), "periods": result_periods, "assignments": assignments}
    return {"range": {"from": date_from.isoformat(), "to": date_to.isoformat()}, "verified_at": timezone.now().isoformat(), "manifest_hash": hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest(), "periods": result_periods, "assignments": assignments, "continuities": [], "changes": []}
