from datetime import date
import uuid

import pytest
from django.contrib.auth import get_user_model

from ros_xolo.core.models import (
    Auditoria,
    Empleado,
    HabilitacionSucursal,
    Organizacion,
    PermisoPlaneacion,
    Rol,
    Sucursal,
)
from ros_xolo.core.services.authorization import ActorContext
from ros_xolo.programacion.models import (
    FilaEmpleadoPublicada,
    JornadaBorrador,
    JornadaPublicada,
)
from ros_xolo.programacion.selectors.planning import get_draft, get_published
from ros_xolo.programacion.services.drafts import replace_draft
from ros_xolo.programacion.services.periods import create_period
from ros_xolo.programacion.services.publication import publish_period
from ros_xolo.programacion.services.validation import ScheduleValidationError


def _scenario():
    user = get_user_model().objects.create_user(username=f"planner-{uuid.uuid4()}")
    organization = Organizacion.objects.create(name="XOLO")
    branch = Sucursal.objects.create(
        organization=organization,
        name="Jaltepec",
        timezone="America/Mexico_City",
    )
    PermisoPlaneacion.objects.create(
        organization=organization,
        user=user,
        branch=branch,
        enabled=True,
    )
    actor = ActorContext(user_id=user.id, organization_id=organization.id)
    period, _, _ = create_period(actor, branch.id, date(2026, 9, 21), date(2026, 9, 27))
    return actor, organization, branch, period


@pytest.mark.django_db(transaction=True)
def test_replace_draft_is_complete_and_semantic_noop_is_not_a_write():
    actor, organization, branch, period = _scenario()
    employee = Empleado.objects.create(
        organization=organization,
        display_name="Ana",
    )
    HabilitacionSucursal.objects.create(
        organization=organization,
        employee=employee,
        branch=branch,
        enabled=True,
    )
    role = Rol.objects.create(organization=organization, name="Cocina")
    role.applicable_branches.add(branch)
    assignment_id = uuid.uuid4()
    break_id = uuid.uuid4()
    payload = [
        {
            "assignment_id": str(assignment_id),
            "employee_id": str(employee.id),
            "starts_at": "2026-09-21T09:00:00-06:00",
            "ends_at": "2026-09-21T17:00:00-06:00",
            "role_id": str(role.id),
            "station_id": None,
            "shift_id": None,
            "breaks": [
                {
                    "break_id": str(break_id),
                    "starts_at": "2026-09-21T13:00:00-06:00",
                    "ends_at": "2026-09-21T13:30:00-06:00",
                }
            ],
        }
    ]

    first = replace_draft(actor, period.id, get_draft(actor, period.id)["etag"], payload)
    audit_count = Auditoria.objects.filter(operation="scheduling.draft.replace").count()
    second = replace_draft(actor, period.id, first["etag"], payload)

    assert first["saved"] is True
    assert second["saved"] is False
    assert second["etag"] == first["etag"]
    assert Auditoria.objects.filter(operation="scheduling.draft.replace").count() == audit_count
    assert JornadaBorrador.objects.get(assignment_id=assignment_id).draft.breaks.count() == 1

    removed = replace_draft(actor, period.id, second["etag"], [])
    assert removed["saved"] is True
    assert not JornadaBorrador.objects.filter(assignment_id=assignment_id).exists()


@pytest.mark.django_db(transaction=True)
def test_empty_period_can_be_published_atomically_and_selected_with_roster_rows():
    actor, organization, branch, period = _scenario()
    employee = Empleado.objects.create(
        organization=organization,
        display_name="Empleado sin jornada",
    )
    HabilitacionSucursal.objects.create(
        organization=organization,
        employee=employee,
        branch=branch,
        enabled=True,
    )
    draft_projection = get_draft(actor, period.id)

    result = publish_period(actor, period.id, draft_projection["etag"])
    projection = get_published(actor, period.id)

    assert result["outcome"] == "published"
    assert result["version"] == 1
    assert JornadaPublicada.objects.filter(publication_id=result["publication_id"]).count() == 0
    assert FilaEmpleadoPublicada.objects.filter(
        publication_id=result["publication_id"], employee=employee
    ).exists()
    assert projection["assignments"] == []
    assert projection["roster"][0]["employee_id"] == str(employee.id)
    assert projection["pending_draft_excluded"] is False
    assert projection["manifest"]["sources"][0]["version"] == 1


@pytest.mark.django_db(transaction=True)
def test_invalid_candidate_rolls_back_and_night_shift_is_a_read_only_continuity():
    actor, organization, branch, origin = _scenario()
    employee = Empleado.objects.create(
        organization=organization,
        display_name="Nocturno",
    )
    HabilitacionSucursal.objects.create(
        organization=organization,
        employee=employee,
        branch=branch,
        enabled=True,
    )
    role = Rol.objects.create(organization=organization, name="Cierre")
    role.applicable_branches.add(branch)
    assignment_id = uuid.uuid4()
    break_id = uuid.uuid4()
    payload = [
        {
            "assignment_id": str(assignment_id),
            "employee_id": str(employee.id),
            "starts_at": "2026-09-27T22:00:00-06:00",
            "ends_at": "2026-09-28T06:00:00-06:00",
            "role_id": str(role.id),
            "station_id": None,
            "shift_id": None,
            "breaks": [
                {
                    "break_id": str(break_id),
                    "starts_at": "2026-09-28T01:00:00-06:00",
                    "ends_at": "2026-09-28T01:30:00-06:00",
                }
            ],
        }
    ]
    etag = get_draft(actor, origin.id)["etag"]
    invalid = [
        {
            **payload[0],
            "breaks": [
                {
                    **payload[0]["breaks"][0],
                    "ends_at": "2026-09-28T07:00:00-06:00",
                }
            ],
        }
    ]

    with pytest.raises(ScheduleValidationError):
        replace_draft(actor, origin.id, etag, invalid)
    assert not JornadaBorrador.objects.filter(assignment_id=assignment_id).exists()

    saved = replace_draft(actor, origin.id, etag, payload)
    published = publish_period(actor, origin.id, saved["etag"])
    destination, _, _ = create_period(
        actor,
        branch.id,
        date(2026, 9, 28),
        date(2026, 10, 4),
    )
    destination_projection = get_draft(actor, destination.id)
    origin_projection = get_published(actor, origin.id)

    assert len(origin_projection["assignments"]) == 1
    assert len(origin_projection["assignments"][0]["breaks"]) == 1
    assert len(destination_projection["continuities"]) == 1
    continuity = destination_projection["continuities"][0]
    assert continuity["read_only"] is True
    assert continuity["origin_period_id"] == str(origin.id)
    assert continuity["origin_publication_id"] == str(published["publication_id"])
    assert continuity["origin_version"] == 1
