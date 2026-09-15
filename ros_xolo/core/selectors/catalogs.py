from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from django.utils.timezone import make_aware
from ros_xolo.core.models import HabilitacionSucursal, Rol, Sucursal, Turno
from ros_xolo.core.services.authorization import authorize_planner


def get_planning_catalogs(actor, branch_id):
    grant = authorize_planner(actor, branch_id)
    branch = grant.branch
    employees = HabilitacionSucursal.objects.filter(organization_id=actor.organization_id, branch=branch, enabled=True, employee__active=True).select_related("employee")
    return {"branch": branch, "core_revision": branch.organization.core_revision, "employees": employees, "roles": Rol.objects.filter(organization_id=actor.organization_id, active=True, applicable_branches=branch), "shifts": Turno.objects.filter(organization_id=actor.organization_id, active=True, applicable_branches=branch)}


def resolve_shift(actor, branch_id, shift_id, start_date, start_offset=None, end_offset=None):
    branch = authorize_planner(actor, branch_id).branch
    shift = Turno.objects.get(pk=shift_id, organization_id=actor.organization_id, active=True, applicable_branches=branch)
    zone = ZoneInfo(branch.timezone)
    start = datetime.combine(start_date, shift.start_local_time)
    end = datetime.combine(start_date + timedelta(days=shift.end_day_offset), shift.end_local_time)
    start = _resolve_local(start, zone, start_offset)
    end = _resolve_local(end, zone, end_offset)
    if end <= start: raise ValueError("El fin debe ser posterior al inicio.")
    return {"shift": shift, "starts_at": start, "ends_at": end}


def _resolve_local(value, zone, offset):
    candidates = [value.replace(tzinfo=zone, fold=fold) for fold in (0, 1)]
    valid = [c for c in candidates if c.astimezone(ZoneInfo("UTC")).astimezone(zone).replace(tzinfo=None) == value]
    if not valid: raise ValueError("Hora local inexistente.")
    if len({c.utcoffset() for c in valid}) > 1:
        if offset is None: raise ValueError("Hora local ambigua: se requiere offset.")
        valid = [c for c in valid if c.utcoffset().total_seconds() == offset]
        if not valid: raise ValueError("Offset incompatible.")
    return valid[0]
