"""T079/T089: synchronous private export HTTP contract."""

import hashlib
from pathlib import Path

import pytest

from ros_xolo.core.models import PermisoPlaneacion
from ros_xolo.programacion.exports.renderer import RenderResult
from ros_xolo.programacion.services.drafts import replace_draft
from ros_xolo.programacion.services.publication import publish_period
from tests.programacion_helpers import assignment_payload, etag, period_for, scenario

pytestmark = pytest.mark.django_db


def _published(data):
    period = period_for(data)
    assignment = assignment_payload(
        data,
        starts_at="2026-09-21T09:00:00-06:00",
        ends_at="2026-09-21T17:00:00-06:00",
    )
    replace_draft(data["actor"], period.id, etag(data, period), {"assignments": [assignment]})
    publish_period(data["actor"], period.id, etag(data, period))
    return period


def _login(client, data):
    client.force_login(data["user"])
    session = client.session
    session["organization_id"] = str(data["organization"].id)
    session.save()


def _fake_renderer(frozen, export_format, destination):
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = b"complete-private-export"
    path.write_bytes(content)
    return RenderResult(
        path=path,
        sha256=hashlib.sha256(content).hexdigest(),
        byte_size=len(content),
        mime_type="image/png" if export_format == "png" else "application/pdf",
    )


def test_export_request_requires_authentication(client):
    response = client.post(
        "/api/v1/planning/periods/00000000-0000-0000-0000-000000000000/exports",
        data={"format": "png"},
        content_type="application/json",
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


def test_export_request_returns_ready_metadata_and_private_download(
    client, monkeypatch, settings, tmp_path
):
    data = scenario()
    period = _published(data)
    _login(client, data)
    settings.EXPORT_STORAGE_ROOT = tmp_path
    monkeypatch.setattr("ros_xolo.programacion.services.exports.render_export", _fake_renderer)

    response = client.post(
        f"/api/v1/planning/periods/{period.id}/exports",
        data={"format": "png"},
        content_type="application/json",
    )

    assert response.status_code == 201
    metadata = response.json()
    assert metadata["status"] == "ready"
    assert metadata["sha256"] == hashlib.sha256(b"complete-private-export").hexdigest()
    assert metadata["download_url"].endswith("/file")

    download = client.get(metadata["download_url"])
    assert download.status_code == 200
    assert download["Content-Type"] == "image/png"
    assert "attachment" in download["Content-Disposition"]
    assert b"".join(download.streaming_content) == b"complete-private-export"


def test_every_status_and_download_request_reauthorizes_current_permission(
    client, monkeypatch, settings, tmp_path
):
    data = scenario()
    period = _published(data)
    _login(client, data)
    settings.EXPORT_STORAGE_ROOT = tmp_path
    monkeypatch.setattr("ros_xolo.programacion.services.exports.render_export", _fake_renderer)
    created = client.post(
        f"/api/v1/planning/periods/{period.id}/exports",
        data={"format": "pdf"},
        content_type="application/json",
    ).json()

    PermisoPlaneacion.objects.filter(user=data["user"], branch=data["branch"]).update(enabled=False)

    assert client.get(f"/api/v1/planning/exports/{created['export_id']}").status_code == 404
    assert client.get(created["download_url"]).status_code == 404


def test_only_png_or_pdf_is_accepted(client):
    data = scenario()
    period = _published(data)
    _login(client, data)
    response = client.post(
        f"/api/v1/planning/periods/{period.id}/exports",
        data={"format": "svg"},
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"
