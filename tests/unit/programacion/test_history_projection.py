import json

import pytest

from ros_xolo.core.models import Empleado, HabilitacionSucursal
from ros_xolo.programacion.selectors.history import get_history, get_personal_history
from ros_xolo.programacion.services.drafts import replace_draft
from ros_xolo.programacion.services.publication import publish_period
from tests.programacion_helpers import assignment_payload, etag, period_for, scenario


@pytest.mark.django_db(transaction=True)
def test_reassignment_is_private_and_historical_labels_are_immutable():
    data = scenario(employee_user=True)
    period = period_for(data)
    payload = assignment_payload(
        data,
        starts_at="2026-09-21T09:00:00-06:00",
        ends_at="2026-09-21T17:00:00-06:00",
    )
    saved = replace_draft(data["actor"], period.id, etag(data, period), [payload])
    first = publish_period(data["actor"], period.id, saved["etag"])
    other = Empleado.objects.create(organization=data["organization"], display_name="Bea")
    HabilitacionSucursal.objects.create(
        organization=data["organization"], employee=other, branch=data["branch"], enabled=True
    )
    revised = {**payload, "employee_id": str(other.id)}
    saved = replace_draft(data["actor"], period.id, first["etag"], [revised])
    publish_period(data["actor"], period.id, saved["etag"])

    personal = get_personal_history(
        data["actor"], period.date_from, period.date_to, limit=50
    )
    rendered = json.dumps(personal)
    assert any(item["kind"] == "assignment_removed" for item in personal["changes"])
    assert str(other.id) not in rendered

    data["role"].name = "Nombre nuevo"
    data["role"].save(update_fields=["name"])
    historical = get_history(data["actor"], period.id, version=1)
    assert historical["assignments"][0]["labels"]["role"] == "Cocina"
