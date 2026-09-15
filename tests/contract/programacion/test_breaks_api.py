"""T072: complete-replacement API contract for break identities and field errors."""

import json
import uuid

import pytest

from tests.programacion_helpers import assignment_payload, etag, period_for, scenario

pytestmark = pytest.mark.django_db


def test_break_payload_preserves_identity_and_returns_a_precise_422_path(client):
    data, period = scenario(), None
    period = period_for(data)
    client.force_login(data["user"])
    session = client.session
    session["organization_id"] = str(data["organization"].id)
    session.save()
    break_id = uuid.uuid4()
    payload = assignment_payload(data, starts_at="2026-09-21T09:00:00-06:00", ends_at="2026-09-21T17:00:00-06:00", breaks=[{"break_id": str(break_id), "starts_at": "2026-09-21T12:00:00-06:00", "ends_at": "2026-09-21T12:30:00-06:00"}])
    response = client.put(f"/api/v1/planning/periods/{period.id}/draft", data=json.dumps({"assignments": [payload]}), content_type="application/json", HTTP_IF_MATCH=etag(data, period))
    assert response.status_code == 200
    assert response.json()["assignments"][0]["breaks"][0]["break_id"] == str(break_id)
    payload["breaks"][0]["ends_at"] = "2026-09-21T12:00:00-06:00"
    response = client.put(f"/api/v1/planning/periods/{period.id}/draft", data=json.dumps({"assignments": [payload]}), content_type="application/json", HTTP_IF_MATCH=response.headers["ETag"])
    assert response.status_code == 422
    assert response.json()["error"]["fields"] == [{"path": "assignments[0].breaks[0].ends_at", "code": "invalid_break"}]
