from datetime import date
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
import threading

import pytest
from django.db import DatabaseError, close_old_connections, transaction

from ros_xolo.core.events.registry import dispatch
from ros_xolo.core.models import Empleado, Evento, HabilitacionSucursal, Incidencia
from ros_xolo.programacion.models import CambioPublicacion, PublicacionProgramacion
from ros_xolo.programacion.selectors.alerts import get_active_alerts
from ros_xolo.programacion.services.drafts import replace_draft
from ros_xolo.programacion.services.drafts import StaleBase
from ros_xolo.programacion.services.publication import publish_period
from tests.programacion_helpers import assignment_payload, etag, period_for, scenario


@pytest.mark.django_db(transaction=True)
def test_revision_creates_immutable_diff_and_failure_before_pointer_rolls_back():
    data = scenario()
    period = period_for(data)
    payload = assignment_payload(
        data,
        starts_at="2026-09-21T09:00:00-06:00",
        ends_at="2026-09-21T17:00:00-06:00",
    )
    saved = replace_draft(data["actor"], period.id, etag(data, period), [payload])
    first = publish_period(data["actor"], period.id, saved["etag"])
    modified = {**payload, "ends_at": "2026-09-21T18:00:00-06:00"}
    saved = replace_draft(data["actor"], period.id, first["etag"], [modified])

    with patch(
        "ros_xolo.programacion.services.publication._before_publication_pointer",
        side_effect=RuntimeError("induced failure"),
    ):
        with pytest.raises(RuntimeError):
            publish_period(data["actor"], period.id, saved["etag"])
    period.refresh_from_db()
    assert period.current_publication_id == first["publication_id"]
    assert PublicacionProgramacion.objects.filter(period=period).count() == 1

    second = publish_period(data["actor"], period.id, saved["etag"])
    assert second["version"] == 2
    assert CambioPublicacion.objects.filter(
        publication_id=second["publication_id"], kind="assignment_modified"
    ).exists()
    assert PublicacionProgramacion.objects.filter(period=period).count() == 2


@pytest.mark.django_db(transaction=True)
def test_roster_only_revision_and_ineligibility_incident_resolution():
    data = scenario()
    period = period_for(data)
    first = publish_period(data["actor"], period.id, etag(data, period))
    new_employee = Empleado.objects.create(
        organization=data["organization"], display_name="Bea"
    )
    HabilitacionSucursal.objects.create(
        organization=data["organization"], employee=new_employee,
        branch=data["branch"], enabled=True
    )
    data["organization"].core_revision += 1
    data["organization"].save(update_fields=["core_revision"])
    second = publish_period(data["actor"], period.id, etag(data, period))
    assert second["version"] == 2
    assert CambioPublicacion.objects.filter(
        publication_id=second["publication_id"], kind="roster_added"
    ).exists()

    future = period_for(
        data, start=date(2036, 9, 21), end=date(2036, 9, 27)
    )
    payload = assignment_payload(
        data,
        starts_at="2036-09-21T09:00:00-06:00",
        ends_at="2036-09-21T17:00:00-06:00",
    )
    saved = replace_draft(data["actor"], future.id, etag(data, future), [payload])
    published = publish_period(data["actor"], future.id, saved["etag"])
    membership = HabilitacionSucursal.objects.get(
        employee=data["employee"], branch=data["branch"]
    )
    membership.enabled = False
    membership.save(update_fields=["enabled"])
    event = Evento.objects.create(
        organization=data["organization"], branch=data["branch"], actor=data["user"],
        type="core.membership_changed", subject_id=membership.id,
        payload={"employee_id": str(data["employee"].id), "enabled": False},
    )
    dispatch(event)
    assert Incidencia.objects.filter(period_id=future.id, status="open").exists()
    assert any(
        alert["type"] == "employee_ineligible_future"
        for alert in get_active_alerts(data["actor"], data["branch"].id)
    )

    membership.enabled = True
    membership.save(update_fields=["enabled"])
    restored = Evento.objects.create(
        organization=data["organization"], branch=data["branch"], actor=data["user"],
        type="core.membership_changed", subject_id=membership.id,
        payload={"employee_id": str(data["employee"].id), "enabled": True},
    )
    dispatch(restored)
    assert not Incidencia.objects.filter(period_id=future.id, status="open").exists()


@pytest.mark.django_db(transaction=True)
def test_two_concurrent_publishers_cannot_create_competing_current_versions():
    data = scenario()
    period = period_for(data)
    payload = assignment_payload(
        data,
        starts_at="2026-09-21T09:00:00-06:00",
        ends_at="2026-09-21T17:00:00-06:00",
    )
    saved = replace_draft(data["actor"], period.id, etag(data, period), [payload])
    first = publish_period(data["actor"], period.id, saved["etag"])
    revised = {**payload, "ends_at": "2026-09-21T18:00:00-06:00"}
    saved = replace_draft(data["actor"], period.id, first["etag"], [revised])
    expected = saved["etag"]
    barrier = threading.Barrier(2)

    def publish():
        close_old_connections()
        barrier.wait(timeout=5)
        try:
            return publish_period(data["actor"], period.id, expected)["outcome"]
        except StaleBase:
            return "stale_base"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(publish), executor.submit(publish)]
        outcomes = sorted(future.result() for future in futures)
    period.refresh_from_db()
    assert outcomes == ["published", "stale_base"]
    assert PublicacionProgramacion.objects.filter(period=period).count() == 2
    assert PublicacionProgramacion.objects.get(pk=period.current_publication_id).version == 2


@pytest.mark.django_db(transaction=True)
def test_published_snapshots_reject_update_and_delete_at_the_database_boundary():
    data = scenario()
    period = period_for(data)
    published = publish_period(data["actor"], period.id, etag(data, period))
    with pytest.raises(DatabaseError), transaction.atomic():
        PublicacionProgramacion.objects.filter(pk=published["publication_id"]).update(
            branch_label="Alterada"
        )
    publication = PublicacionProgramacion.objects.get(pk=published["publication_id"])
    assert publication.branch_label == "Jaltepec"
