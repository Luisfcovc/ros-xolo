from concurrent.futures import ThreadPoolExecutor
from datetime import date
import threading

import pytest
from django.db import close_old_connections

from ros_xolo.programacion.services.conflicts import OverlapConflict
from ros_xolo.programacion.services.drafts import replace_draft
from ros_xolo.programacion.services.publication import publish_period
from tests.programacion_helpers import assignment_payload, etag, period_for, scenario


@pytest.mark.django_db(transaction=True)
def test_current_publication_and_other_active_draft_block_across_periods_and_branches():
    data = scenario(two_branches=True)
    origin = period_for(data)
    destination = period_for(data, branch=data["other_branch"])
    payload = assignment_payload(
        data,
        starts_at="2026-09-21T10:00:00-06:00",
        ends_at="2026-09-21T18:00:00-06:00",
    )
    saved = replace_draft(data["actor"], origin.id, etag(data, origin), [payload])
    candidate = assignment_payload(
        data,
        starts_at="2026-09-21T12:00:00-04:00",
        ends_at="2026-09-21T14:00:00-04:00",
    )
    with pytest.raises(OverlapConflict):
        replace_draft(data["actor"], destination.id, etag(data, destination), [candidate])
    publish_period(data["actor"], origin.id, saved["etag"])
    with pytest.raises(OverlapConflict):
        replace_draft(data["actor"], destination.id, etag(data, destination), [candidate])


@pytest.mark.django_db(transaction=True)
def test_synchronized_writes_use_independent_connections_and_only_one_commits():
    data = scenario(two_branches=True)
    first = period_for(data)
    second = period_for(data, branch=data["other_branch"])
    first_etag, second_etag = etag(data, first), etag(data, second)
    barrier = threading.Barrier(2)

    def save(period, expected, payload):
        close_old_connections()
        barrier.wait(timeout=5)
        try:
            replace_draft(data["actor"], period.id, expected, [payload])
            return "saved"
        except OverlapConflict:
            return "overlap"
        finally:
            close_old_connections()

    a = assignment_payload(
        data,
        starts_at="2026-09-21T09:00:00-06:00",
        ends_at="2026-09-21T17:00:00-06:00",
    )
    b = assignment_payload(
        data,
        starts_at="2026-09-21T11:00:00-04:00",
        ends_at="2026-09-21T15:00:00-04:00",
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(save, first, first_etag, a),
            executor.submit(save, second, second_etag, b),
        ]
        outcomes = sorted(future.result() for future in futures)
    assert outcomes == ["overlap", "saved"]
