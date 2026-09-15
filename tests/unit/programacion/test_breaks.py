"""T071: domain coverage for optional, bounded schedule breaks."""

import uuid

import pytest

from ros_xolo.programacion.services.drafts import replace_draft
from ros_xolo.programacion.services.validation import ScheduleValidationError
from tests.programacion_helpers import assignment_payload, etag, period_for, scenario

pytestmark = pytest.mark.django_db


def _break(starts_at, ends_at):
    return {"break_id": str(uuid.uuid4()), "starts_at": starts_at, "ends_at": ends_at}


def test_breaks_are_optional_and_accept_adjacent_schedule_edges():
    data, period = scenario(), None
    period = period_for(data)
    payload = assignment_payload(data, starts_at="2026-09-21T09:00:00-06:00", ends_at="2026-09-21T17:00:00-06:00", breaks=[_break("2026-09-21T09:00:00-06:00", "2026-09-21T09:15:00-06:00"), _break("2026-09-21T16:45:00-06:00", "2026-09-21T17:00:00-06:00")])
    assert replace_draft(data["actor"], period.id, etag(data, period), [payload])["saved"]


@pytest.mark.parametrize("breaks", [
    [_break("2026-09-21T10:00:00-06:00", "2026-09-21T10:00:00-06:00")],
    [_break("2026-09-21T08:59:00-06:00", "2026-09-21T10:00:00-06:00")],
    [_break("2026-09-21T10:00:00-06:00", "2026-09-21T11:00:00-06:00"), _break("2026-09-21T10:30:00-06:00", "2026-09-21T11:30:00-06:00")],
])
def test_breaks_must_be_positive_contained_and_non_overlapping(breaks):
    data, period = scenario(), None
    period = period_for(data)
    payload = assignment_payload(data, starts_at="2026-09-21T09:00:00-06:00", ends_at="2026-09-21T17:00:00-06:00", breaks=breaks)
    with pytest.raises(ScheduleValidationError) as error:
        replace_draft(data["actor"], period.id, etag(data, period), [payload])
    assert error.value.code == "invalid_break"


def test_shortening_a_schedule_that_excludes_its_break_is_rejected():
    data, period = scenario(), None
    period = period_for(data)
    assignment_id = uuid.uuid4()
    original = assignment_payload(data, assignment_id=assignment_id, starts_at="2026-09-21T09:00:00-06:00", ends_at="2026-09-21T17:00:00-06:00", breaks=[_break("2026-09-21T16:00:00-06:00", "2026-09-21T16:30:00-06:00")])
    saved = replace_draft(data["actor"], period.id, etag(data, period), [original])
    shorter = {**original, "ends_at": "2026-09-21T16:15:00-06:00"}
    with pytest.raises(ScheduleValidationError):
        replace_draft(data["actor"], period.id, saved["etag"], [shorter])
