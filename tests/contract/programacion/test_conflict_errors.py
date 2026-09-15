import json

import pytest
from django.test import Client

from ros_xolo.core.models import PermisoPlaneacion
from ros_xolo.programacion.services.drafts import replace_draft
from tests.programacion_helpers import assignment_payload, etag, period_for, scenario


@pytest.mark.django_db(transaction=True)
def test_overlap_is_409_and_restricted_origin_is_fully_redacted():
    data = scenario(two_branches=True)
    origin = period_for(data, branch=data["other_branch"])
    target = period_for(data)
    existing = assignment_payload(
        data,
        starts_at="2026-09-21T11:00:00-04:00",
        ends_at="2026-09-21T15:00:00-04:00",
    )
    replace_draft(data["actor"], origin.id, etag(data, origin), [existing])
    PermisoPlaneacion.objects.filter(branch=data["other_branch"]).update(enabled=False)

    client = Client()
    client.force_login(data["user"])
    session = client.session
    session["organization_id"] = str(data["organization"].id)
    session.save()
    candidate = assignment_payload(
        data,
        starts_at="2026-09-21T09:00:00-06:00",
        ends_at="2026-09-21T17:00:00-06:00",
    )
    response = client.put(
        f"/api/v1/planning/periods/{target.id}/draft",
        data=json.dumps({"assignments": [candidate]}),
        content_type="application/json",
        HTTP_IF_MATCH=etag(data, target),
    )
    body = response.json()
    rendered = json.dumps(body)
    assert response.status_code == 409
    assert body["error"]["code"] == "overlap"
    assert "coordina" in body["error"]["action"].lower()
    for secret in (str(origin.id), str(data["other_branch"].id), "Centro", "11:00", "15:00"):
        assert secret not in rendered
