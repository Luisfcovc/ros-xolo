from datetime import date
import uuid

from django.contrib.auth import get_user_model

from ros_xolo.core.models import (
    Empleado,
    HabilitacionSucursal,
    Organizacion,
    PermisoPlaneacion,
    Rol,
    Sucursal,
    UsuarioOrganizacion,
)
from ros_xolo.core.services.authorization import ActorContext
from ros_xolo.programacion.selectors.planning import get_draft
from ros_xolo.programacion.services.periods import create_period


def scenario(*, two_branches=False, employee_user=False):
    suffix = uuid.uuid4()
    user = get_user_model().objects.create_user(username=f"planner-{suffix}")
    organization = Organizacion.objects.create(name="XOLO")
    branch = Sucursal.objects.create(
        organization=organization,
        name="Jaltepec",
        timezone="America/Mexico_City",
    )
    PermisoPlaneacion.objects.create(
        organization=organization, user=user, branch=branch, enabled=True
    )
    actor = ActorContext(user_id=user.id, organization_id=organization.id)
    employee = Empleado.objects.create(organization=organization, display_name="Ana")
    HabilitacionSucursal.objects.create(
        organization=organization, employee=employee, branch=branch, enabled=True
    )
    if employee_user:
        UsuarioOrganizacion.objects.create(
            organization=organization, user=user, employee=employee, active=True
        )
    role = Rol.objects.create(organization=organization, name="Cocina")
    role.applicable_branches.add(branch)
    result = {
        "user": user,
        "actor": actor,
        "organization": organization,
        "branch": branch,
        "employee": employee,
        "role": role,
    }
    if two_branches:
        other = Sucursal.objects.create(
            organization=organization,
            name="Centro",
            timezone="America/New_York",
        )
        PermisoPlaneacion.objects.create(
            organization=organization, user=user, branch=other, enabled=True
        )
        HabilitacionSucursal.objects.create(
            organization=organization, employee=employee, branch=other, enabled=True
        )
        role.applicable_branches.add(other)
        result["other_branch"] = other
    return result


def period_for(data, *, branch=None, start=date(2026, 9, 21), end=date(2026, 9, 27)):
    period, _, _ = create_period(
        data["actor"], (branch or data["branch"]).id, start, end
    )
    return period


def assignment_payload(data, *, starts_at, ends_at, assignment_id=None, breaks=None):
    return {
        "assignment_id": str(assignment_id or uuid.uuid4()),
        "employee_id": str(data["employee"].id),
        "starts_at": starts_at,
        "ends_at": ends_at,
        "role_id": str(data["role"].id),
        "station_id": None,
        "shift_id": None,
        "breaks": breaks or [],
    }


def etag(data, period):
    return get_draft(data["actor"], period.id)["etag"]
