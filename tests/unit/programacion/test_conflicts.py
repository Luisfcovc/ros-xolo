import pytest

from ros_xolo.programacion.services.conflicts import OverlapConflict, intervals_overlap
from ros_xolo.programacion.selectors.alerts import overlap_alert
from ros_xolo.programacion.services.drafts import replace_draft
from tests.programacion_helpers import assignment_payload, etag, period_for, scenario


@pytest.mark.parametrize(
    ("a_start", "a_end", "b_start", "b_end", "expected"),
    [
        (0, 10, 10, 20, False),
        (0, 10, 9, 20, True),
        (0, 10, 0, 10, True),
    ],
)
def test_intervals_are_semiclosed(a_start, a_end, b_start, b_end, expected):
    assert intervals_overlap(a_start, a_end, b_start, b_end) is expected


def test_overlap_alert_has_priority_scope_and_required_action():
    error = OverlapConflict(
        fields=[{"path": "assignments[0].starts_at", "code": "overlap"}],
        conflicts=[{"restricted": True, "scope": "draft"}],
    )
    alert = overlap_alert(error, period_id="period-a")
    assert alert["priority"] == "high"
    assert alert["context"]["conflicts"] == [{"restricted": True, "scope": "draft"}]
    assert "coordina" in alert["required_action"].lower()


@pytest.mark.django_db(transaction=True)
def test_duplicate_midnight_and_breaks_do_not_release_reserved_time():
    data = scenario()
    period = period_for(data)
    first = assignment_payload(
        data,
        starts_at="2026-09-21T22:00:00-06:00",
        ends_at="2026-09-22T06:00:00-06:00",
        breaks=[{
            "break_id": "aaaaaaaa-0000-4000-8000-000000000001",
            "starts_at": "2026-09-22T01:00:00-06:00",
            "ends_at": "2026-09-22T01:30:00-06:00",
        }],
    )
    duplicate = assignment_payload(
        data,
        starts_at="2026-09-21T22:00:00-06:00",
        ends_at="2026-09-22T06:00:00-06:00",
    )
    during_break = assignment_payload(
        data,
        starts_at="2026-09-22T01:00:00-06:00",
        ends_at="2026-09-22T01:30:00-06:00",
    )

    with pytest.raises(OverlapConflict):
        replace_draft(data["actor"], period.id, etag(data, period), [first, duplicate])
    with pytest.raises(OverlapConflict):
        replace_draft(data["actor"], period.id, etag(data, period), [first, during_break])


@pytest.mark.django_db(transaction=True)
def test_adjacency_is_allowed_and_own_version_can_be_replaced():
    data = scenario()
    period = period_for(data)
    first = assignment_payload(
        data,
        starts_at="2026-09-21T09:00:00-06:00",
        ends_at="2026-09-21T17:00:00-06:00",
    )
    adjacent = assignment_payload(
        data,
        starts_at="2026-09-21T17:00:00-06:00",
        ends_at="2026-09-21T21:00:00-06:00",
    )
    saved = replace_draft(data["actor"], period.id, etag(data, period), [first, adjacent])
    modified = {**first, "starts_at": "2026-09-21T08:00:00-06:00"}
    result = replace_draft(data["actor"], period.id, saved["etag"], [modified, adjacent])
    assert result["saved"] is True
