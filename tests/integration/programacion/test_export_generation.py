"""T080/T084–T088: Q6 frozen rendering and failure lifecycle."""

import hashlib
from datetime import timedelta
from pathlib import Path

import pytest
from django.utils import timezone

from ros_xolo.core.models import Auditoria, Evento
from ros_xolo.programacion.exports.renderer import ExportTimeout, RenderResult
from ros_xolo.programacion.models import ExportacionProgramacion
from ros_xolo.programacion.services.drafts import replace_draft
from ros_xolo.programacion.services.exports import (
    get_export_file,
    purge_expired_exports,
    request_export,
)
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
    return period, assignment


@pytest.mark.parametrize(
    ("export_format", "signature"), [("png", b"\x89PNG\r\n\x1a\n"), ("pdf", b"%PDF-")]
)
def test_real_renderer_produces_valid_private_png_and_pdf(settings, tmp_path, export_format, signature):
    data = scenario()
    period, _ = _published(data)
    settings.EXPORT_STORAGE_ROOT = tmp_path

    export = request_export(data["actor"], period.id, export_format)
    stored, path = get_export_file(data["actor"], export.id)

    assert stored.status == ExportacionProgramacion.READY
    assert path.read_bytes().startswith(signature)
    assert stored.byte_size == path.stat().st_size
    assert stored.content_hash == hashlib.sha256(path.read_bytes()).hexdigest()
    assert Evento.objects.filter(type="scheduling.export_ready", subject_id=stored.id).exists()
    assert Auditoria.objects.filter(
        operation="scheduling.export.generate", subject_id=stored.id, outcome="success"
    ).exists()


def test_export_keeps_its_frozen_publication_when_a_new_version_is_published_during_render(
    monkeypatch, settings, tmp_path
):
    data = scenario()
    period, assignment = _published(data)
    period.refresh_from_db()
    first_publication_id = str(period.current_publication_id)
    settings.EXPORT_STORAGE_ROOT = tmp_path

    def publish_during_render(frozen, export_format, destination):
        changed = {**assignment, "ends_at": "2026-09-21T18:00:00-06:00"}
        replace_draft(data["actor"], period.id, etag(data, period), {"assignments": [changed]})
        publish_period(data["actor"], period.id, etag(data, period))
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = b"frozen-v1"
        path.write_bytes(content)
        return RenderResult(
            path=path,
            sha256=hashlib.sha256(content).hexdigest(),
            byte_size=len(content),
            mime_type="image/png",
        )

    monkeypatch.setattr(
        "ros_xolo.programacion.services.exports.render_export", publish_during_render
    )
    export = request_export(data["actor"], period.id, "png")
    period.refresh_from_db()

    assert export.manifest["sources"][0]["publication_id"] == first_publication_id
    assert export.manifest["sources"][0]["version"] == 1
    assert str(period.current_publication_id) != first_publication_id


def test_timeout_marks_failed_and_removes_partial_file(monkeypatch, settings, tmp_path):
    data = scenario()
    period, _ = _published(data)
    settings.EXPORT_STORAGE_ROOT = tmp_path

    def time_out(frozen, export_format, destination):
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"partial")
        raise ExportTimeout("timeout")

    monkeypatch.setattr("ros_xolo.programacion.services.exports.render_export", time_out)
    with pytest.raises(ExportTimeout):
        request_export(data["actor"], period.id, "png")

    export = ExportacionProgramacion.objects.latest("requested_at")
    assert export.status == ExportacionProgramacion.FAILED
    assert export.error_code == "export_timeout"
    assert export.private_storage_key is None
    assert not list(tmp_path.rglob("*.png"))
    assert Evento.objects.filter(type="scheduling.export_failed", subject_id=export.id).exists()
    assert Auditoria.objects.filter(subject_id=export.id, outcome="failed").exists()


def test_purge_marks_expired_and_removes_private_bytes(monkeypatch, settings, tmp_path):
    data = scenario()
    period, _ = _published(data)
    settings.EXPORT_STORAGE_ROOT = tmp_path

    def completed(frozen, export_format, destination):
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = b"expired-copy"
        path.write_bytes(content)
        return RenderResult(
            path=path,
            sha256=hashlib.sha256(content).hexdigest(),
            byte_size=len(content),
            mime_type="application/pdf",
        )

    monkeypatch.setattr("ros_xolo.programacion.services.exports.render_export", completed)
    export = request_export(data["actor"], period.id, "pdf")
    _, path = get_export_file(data["actor"], export.id)
    export.expires_at = timezone.now() - timedelta(seconds=1)
    export.save(update_fields=["expires_at"])

    result = purge_expired_exports()
    export.refresh_from_db()

    assert result["expired"] == 1
    assert export.status == ExportacionProgramacion.EXPIRED
    assert not path.exists()
