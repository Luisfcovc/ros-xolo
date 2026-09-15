"""T078: export record state and retention metadata."""

import uuid

import pytest

from django.template.loader import render_to_string
from django.utils import timezone

from ros_xolo.programacion.exports.payload import build_export_payload
from ros_xolo.programacion.exports.validation import ExportValidationError, validate_dom_snapshot
from ros_xolo.programacion.models import ExportacionProgramacion
from ros_xolo.programacion.services.drafts import replace_draft
from ros_xolo.programacion.services.publication import publish_period
from tests.programacion_helpers import assignment_payload, etag, period_for, scenario

pytestmark = pytest.mark.django_db


def test_export_record_starts_generating_with_frozen_metadata_and_24_hour_expiry():
    data = scenario()
    period = period_for(data)
    before = timezone.now()
    export = ExportacionProgramacion.objects.create(
        organization=data["organization"], branch=data["branch"], period=period,
        requested_by=data["user"], format=ExportacionProgramacion.PNG,
        manifest={"sources": [{"version": 1}]}, expected_counts={"rows": 1, "breaks": 2},
        pending_draft_excluded=True,
    )
    assert export.id and export.status == ExportacionProgramacion.GENERATING
    assert export.manifest["sources"][0]["version"] == 1
    assert 23 * 60 < (export.expires_at - before).total_seconds() / 60 <= 24 * 60 + 1


def test_ready_export_requires_hash_and_private_key_at_the_database_boundary():
    data = scenario()
    period = period_for(data)
    export = ExportacionProgramacion.objects.create(
        organization=data["organization"], branch=data["branch"], period=period,
        requested_by=data["user"], format=ExportacionProgramacion.PDF,
    )
    export.status = ExportacionProgramacion.READY
    export.content_hash = "a" * 64
    export.private_storage_key = f"exports/{uuid.uuid4()}.pdf"
    export.save(update_fields=["status", "content_hash", "private_storage_key"])
    assert export.status == ExportacionProgramacion.READY


def _published_period_with_break(data):
    period = period_for(data)
    break_id = uuid.uuid4()
    assignment = assignment_payload(
        data,
        starts_at="2026-09-21T09:00:00-06:00",
        ends_at="2026-09-21T17:00:00-06:00",
        breaks=[{
            "break_id": str(break_id),
            "starts_at": "2026-09-21T13:00:00-06:00",
            "ends_at": "2026-09-21T13:30:00-06:00",
        }],
    )
    replace_draft(data["actor"], period.id, etag(data, period), {"assignments": [assignment]})
    publish_period(data["actor"], period.id, etag(data, period))
    return period, assignment, break_id


def test_frozen_payload_has_every_day_row_assignment_break_and_is_immutable():
    data = scenario()
    period, assignment, break_id = _published_period_with_break(data)
    period.refresh_from_db()

    frozen = build_export_payload(data["actor"], period.id)

    assert frozen.expected_counts == {
        "rows": 1,
        "days": 7,
        "assignments": 1,
        "breaks": 1,
        "continuities": 0,
        "continuity_breaks": 0,
    }
    assert frozen.expected_ids["assignments"] == (assignment["assignment_id"],)
    assert frozen.expected_ids["breaks"] == (str(break_id),)
    assert frozen.manifest["sources"][0]["publication_id"] == str(period.current_publication_id)
    with pytest.raises(TypeError):
        frozen.payload["period"] = {}


def test_export_template_autoescapes_labels_and_contains_all_integrity_markers():
    data = scenario()
    data["employee"].display_name = "<script>alert(1)</script>"
    data["employee"].save(update_fields=["display_name"])
    period, assignment, break_id = _published_period_with_break(data)
    frozen = build_export_payload(data["actor"], period.id)

    html = render_to_string(
        "programacion/export.html", {"export": frozen.to_dict(), "export_format": "png"}
    )

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert assignment["assignment_id"] in html
    assert str(break_id) in html
    assert "Copia estática. Consulta la versión vigente en ROS-XOLO" in html


def test_dom_validation_rejects_an_omitted_identifier_even_when_counts_match():
    expected_counts = {"rows": 1}
    expected_ids = {"rows": ["employee-a"]}
    with pytest.raises(ExportValidationError):
        validate_dom_snapshot(
            {"counts": {"rows": 1}, "ids": {"rows": ["employee-b"]}},
            expected_counts,
            expected_ids,
        )
