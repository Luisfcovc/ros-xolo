import json

import pytest
from django.test import Client

from ros_xolo.programacion.services.drafts import replace_draft
from ros_xolo.programacion.services.publication import publish_period
from tests.programacion_helpers import assignment_payload, etag, period_for, scenario


def _client(data):
    client = Client()
    client.force_login(data["user"])
    session = client.session
    session["organization_id"] = str(data["organization"].id)
    session.save()
    return client


@pytest.mark.django_db(transaction=True)
def test_versions_are_paginated_and_limit_is_capped_at_200():
    data = scenario()
    period = period_for(data)
    first = publish_period(data["actor"], period.id, etag(data, period))
    client = _client(data)
    response = client.get(f"/api/v1/planning/periods/{period.id}/versions?limit=201")
    assert response.status_code == 400
    response = client.get(f"/api/v1/planning/periods/{period.id}/versions?limit=50")
    assert response.status_code == 200
    assert response.json()["versions"][0]["version"] == first["version"]
    assert response.json()["next_cursor"] is None


@pytest.mark.django_db(transaction=True)
def test_no_changes_is_200_and_stale_publish_is_412():
    data = scenario()
    period = period_for(data)
    stale = etag(data, period)
    first = publish_period(data["actor"], period.id, stale)
    client = _client(data)
    no_change = client.post(
        f"/api/v1/planning/periods/{period.id}/publish",
        data=json.dumps({}),
        content_type="application/json",
        HTTP_IF_MATCH=first["etag"],
    )
    stale_response = client.post(
        f"/api/v1/planning/periods/{period.id}/publish",
        data=json.dumps({}),
        content_type="application/json",
        HTTP_IF_MATCH=stale,
    )
    assert no_change.status_code == 200
    assert no_change.json()["outcome"] == "no_changes"
    assert no_change.json()["version"] == 1
    assert stale_response.status_code == 412
