"""Authorized collective planning projections."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, time, timedelta, timezone as datetime_timezone
from zoneinfo import ZoneInfo

from django.utils import timezone

from ros_xolo.core.models import Empleado, HabilitacionSucursal
from ros_xolo.core.services.authorization import authorize_planner
from ros_xolo.programacion.models import (
    DescansoPublicado,
    JornadaPublicada,
    PeriodoProgramacion,
    PublicacionProgramacion,
)
from ros_xolo.programacion.services.drafts import make_period_etag
from ros_xolo.programacion.services.validation import canonical_draft
from ros_xolo.programacion.selectors.alerts import get_active_alerts, pending_publication_alert


class NotPublished(ValueError):
    code = "not_published"


def _load_period(actor, period_id):
    period = PeriodoProgramacion.objects.select_related("organization", "branch", "draft").get(
        pk=period_id,
        organization_id=actor.organization_id,
    )
    authorize_planner(actor, period.branch_id)
    return period


def _period_dict(period):
    return {
        "id": str(period.id),
        "branch_id": str(period.branch_id),
        "branch_label": period.branch.name,
        "date_from": period.date_from.isoformat(),
        "date_to": period.date_to.isoformat(),
        "timezone": period.timezone,
    }


def _publication_dict(publication, *, current=True):
    if publication is None:
        return None
    return {
        "id": str(publication.id),
        "version": publication.version,
        "previous_publication_id": (
            str(publication.previous_publication_id)
            if publication.previous_publication_id
            else None
        ),
        "publisher_label": publication.publisher_label,
        "published_at": publication.published_at.isoformat(),
        "content_hash": publication.content_hash,
        "is_current_at_verification": current,
    }


def _serialize_break(row, *, published=False):
    return {
        "break_id": str(row.break_id if published else row.id),
        "starts_at": row.starts_at.astimezone(datetime_timezone.utc).isoformat(),
        "ends_at": row.ends_at.astimezone(datetime_timezone.utc).isoformat(),
        "start_local": _local_value(row.starts_at, row.start_offset),
        "end_local": _local_value(row.ends_at, row.end_offset),
        "start_offset": row.start_offset,
        "end_offset": row.end_offset,
    }


def _local_value(instant, offset_seconds):
    return (
        instant.astimezone(datetime_timezone.utc) + timedelta(seconds=offset_seconds)
    ).replace(tzinfo=None).isoformat()


def _serialize_draft_assignments(draft):
    breaks = {}
    for row in draft.breaks.order_by("starts_at", "id"):
        breaks.setdefault(row.assignment_id, []).append(_serialize_break(row))
    return [
        {
            "assignment_id": str(row.assignment_id),
            "employee_id": str(row.employee_id),
            "starts_at": row.starts_at.astimezone(datetime_timezone.utc).isoformat(),
            "ends_at": row.ends_at.astimezone(datetime_timezone.utc).isoformat(),
            "start_local": _local_value(row.starts_at, row.start_offset),
            "end_local": _local_value(row.ends_at, row.end_offset),
            "start_offset": row.start_offset,
            "end_offset": row.end_offset,
            "timezone": row.timezone,
            "role_id": str(row.role_id) if row.role_id else None,
            "station_id": str(row.station_id) if row.station_id else None,
            "shift_id": str(row.shift_id) if row.shift_id else None,
            "labels": row.labels,
            "breaks": breaks.get(row.assignment_id, []),
        }
        for row in draft.assignments.order_by("starts_at", "assignment_id")
    ]


def _serialize_published_assignments(publication):
    breaks = {}
    for row in publication.breaks.order_by("starts_at", "break_id"):
        breaks.setdefault(row.assignment_id, []).append(_serialize_break(row, published=True))
    return [
        {
            "assignment_id": str(row.assignment_id),
            "employee_id": str(row.employee_id),
            "branch_id": str(row.branch_id),
            "starts_at": row.starts_at.astimezone(datetime_timezone.utc).isoformat(),
            "ends_at": row.ends_at.astimezone(datetime_timezone.utc).isoformat(),
            "start_local": _local_value(row.starts_at, row.start_offset),
            "end_local": _local_value(row.ends_at, row.end_offset),
            "start_offset": row.start_offset,
            "end_offset": row.end_offset,
            "timezone": row.timezone,
            "role_id": str(row.role_id) if row.role_id else None,
            "station_id": str(row.station_id) if row.station_id else None,
            "shift_id": str(row.shift_id) if row.shift_id else None,
            "labels": row.labels,
            "breaks": breaks.get(row.assignment_id, []),
        }
        for row in publication.assignments.order_by("starts_at", "assignment_id")
    ]


def _effective_roster(period):
    employees = {
        membership.employee_id: membership.employee
        for membership in HabilitacionSucursal.objects.filter(
            organization_id=period.organization_id,
            branch_id=period.branch_id,
            enabled=True,
            employee__active=True,
        ).select_related("employee")
    }
    for employee in Empleado.objects.filter(
        id__in=period.draft.assignments.values("employee_id"),
        organization_id=period.organization_id,
    ):
        employees[employee.id] = employee
    ordered = sorted(
        employees.values(),
        key=lambda employee: (employee.display_name.casefold(), str(employee.id)),
    )
    enabled_ids = set(
        HabilitacionSucursal.objects.filter(
            organization_id=period.organization_id,
            branch_id=period.branch_id,
            enabled=True,
            employee__active=True,
        ).values_list("employee_id", flat=True)
    )
    return [
        {
            "employee_id": str(employee.id),
            "employee_label": employee.display_name,
            "enabled": employee.id in enabled_ids,
            "display_order": index,
        }
        for index, employee in enumerate(ordered)
    ]


def _published_roster(publication):
    return [
        {
            "employee_id": str(row.employee_id),
            "employee_label": row.employee_label,
            "display_order": row.display_order,
        }
        for row in publication.roster.order_by("display_order", "employee_id")
    ]


def _range_bounds(period):
    zone = ZoneInfo(period.timezone)
    start = datetime.combine(period.date_from, time.min, tzinfo=zone)
    end = datetime.combine(period.date_to + timedelta(days=1), time.min, tzinfo=zone)
    return start.astimezone(datetime_timezone.utc), end.astimezone(datetime_timezone.utc)


def _continuities(period):
    range_start, range_end = _range_bounds(period)
    origin_periods = list(
        PeriodoProgramacion.objects.filter(
            organization_id=period.organization_id,
            branch_id=period.branch_id,
            current_publication_id__isnull=False,
        )
        .exclude(pk=period.id)
        .only("id", "current_publication_id")
    )
    publication_to_period = {
        item.current_publication_id: item.id for item in origin_periods
    }
    if not publication_to_period:
        return [], {}

    publications = {
        item.id: item
        for item in PublicacionProgramacion.objects.filter(
            id__in=publication_to_period,
            organization_id=period.organization_id,
        )
    }
    rows = (
        JornadaPublicada.objects.filter(
            organization_id=period.organization_id,
            publication_id__in=publication_to_period,
            starts_at__lt=range_end,
            ends_at__gt=range_start,
        )
        .select_related("publication")
        .order_by("starts_at", "assignment_id")
    )
    break_rows = DescansoPublicado.objects.filter(
        publication_id__in=publication_to_period,
        assignment_id__in=rows.values("assignment_id"),
    ).order_by("starts_at", "break_id")
    breaks = {}
    for break_row in break_rows:
        breaks.setdefault((break_row.publication_id, break_row.assignment_id), []).append(
            _serialize_break(break_row, published=True)
        )

    result = []
    used_sources = {}
    for row in rows:
        publication = publications.get(row.publication_id)
        if publication is None:
            continue
        origin_period_id = publication_to_period[row.publication_id]
        used_sources[publication.id] = {
            "period_id": str(origin_period_id),
            "publication_id": str(publication.id),
            "version": publication.version,
        }
        result.append(
            {
                "assignment_id": str(row.assignment_id),
                "employee_id": str(row.employee_id),
                "starts_at": row.starts_at.astimezone(datetime_timezone.utc).isoformat(),
                "ends_at": row.ends_at.astimezone(datetime_timezone.utc).isoformat(),
                "start_local": _local_value(row.starts_at, row.start_offset),
                "end_local": _local_value(row.ends_at, row.end_offset),
                "start_offset": row.start_offset,
                "end_offset": row.end_offset,
                "timezone": row.timezone,
                "role_id": str(row.role_id) if row.role_id else None,
                "station_id": str(row.station_id) if row.station_id else None,
                "shift_id": str(row.shift_id) if row.shift_id else None,
                "labels": row.labels,
                "breaks": breaks.get((row.publication_id, row.assignment_id), []),
                "origin_period_id": str(origin_period_id),
                "origin_publication_id": str(publication.id),
                "origin_version": publication.version,
                "visible_from": max(row.starts_at, range_start).isoformat(),
                "visible_to": min(row.ends_at, range_end).isoformat(),
                "read_only": True,
            }
        )
    return result, used_sources


def _draft_content_hash(period, roster):
    canonical_roster = [
        {
            "employee_id": row["employee_id"],
            "employee_label": row["employee_label"],
        }
        for row in roster
    ]
    material = {
        "roster": canonical_roster,
        "assignments": canonical_draft(period.draft),
    }
    return hashlib.sha256(
        json.dumps(
            material,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def _has_pending_changes(period, roster, publication=None):
    if publication is None:
        return True
    return _draft_content_hash(period, roster) != publication.content_hash


def _manifest(period, publication, origin_sources, verified_at):
    sources = []
    if publication is not None:
        sources.append(
            {
                "period_id": str(period.id),
                "publication_id": str(publication.id),
                "version": publication.version,
            }
        )
    sources.extend(origin_sources.values())
    sources.sort(key=lambda item: (item["period_id"], item["publication_id"]))
    hash_material = {
        "organization_id": str(period.organization_id),
        "branch_id": str(period.branch_id),
        "date_from": period.date_from.isoformat(),
        "date_to": period.date_to.isoformat(),
        "selected_period_id": str(period.id),
        "selected_publication_id": str(publication.id) if publication else None,
        "sources": sources,
    }
    manifest_hash = hashlib.sha256(
        json.dumps(hash_material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        **hash_material,
        "sources": sources,
        "verified_at": verified_at.isoformat(),
        "manifest_hash": manifest_hash,
    }


def list_periods(actor, branch_id, date_from=None, date_to=None):
    authorize_planner(actor, branch_id)
    queryset = PeriodoProgramacion.objects.filter(
        organization_id=actor.organization_id,
        branch_id=branch_id,
    ).select_related("branch")
    if date_from is not None:
        queryset = queryset.filter(date_to__gte=date_from)
    if date_to is not None:
        queryset = queryset.filter(date_from__lte=date_to)

    publication_ids = [
        value
        for value in queryset.values_list("current_publication_id", flat=True)
        if value is not None
    ]
    versions = dict(
        PublicacionProgramacion.objects.filter(id__in=publication_ids).values_list("id", "version")
    )
    return [
        {
            **_period_dict(period),
            "publication_state": "published" if period.current_publication_id else "not_published",
            "status": (
                "published"
                if period.current_publication_id
                else "initial_publication_pending"
            ),
            "current_version": versions.get(period.current_publication_id),
            "edit_revision": period.edit_revision,
        }
        for period in queryset.order_by("date_from", "id")
    ]


def get_draft(actor, period_id):
    period = _load_period(actor, period_id)
    draft = period.draft
    roster = _effective_roster(period)
    publication = None
    if period.current_publication_id:
        publication = PublicacionProgramacion.objects.get(
            pk=period.current_publication_id,
            organization_id=period.organization_id,
            period=period,
        )
    pending = _has_pending_changes(period, roster, publication)
    continuities, _ = _continuities(period)
    alerts = get_active_alerts(actor, period.branch_id, period_id=period.id)
    pending_alert = pending_publication_alert(period, pending)
    if pending_alert:
        alerts.append(pending_alert)
    return {
        "period": _period_dict(period),
        "base_publication": _publication_dict(publication),
        "edit_revision": period.edit_revision,
        "core_revision": period.organization.core_revision,
        "etag": make_period_etag(period),
        "assignments": _serialize_draft_assignments(draft),
        "roster": roster,
        "continuities": continuities,
        "has_pending_changes": pending,
        "alerts": alerts,
    }


def get_published(actor, period_id):
    period = _load_period(actor, period_id)
    if period.current_publication_id is None:
        raise NotPublished("not_published")
    publication = PublicacionProgramacion.objects.get(
        pk=period.current_publication_id,
        organization_id=period.organization_id,
        period=period,
    )
    continuities, sources = _continuities(period)
    verified_at = timezone.now()
    current_roster = _effective_roster(period)
    pending = _has_pending_changes(period, current_roster, publication)
    return {
        "period": _period_dict(period),
        "publication": _publication_dict(publication),
        "roster": _published_roster(publication),
        "assignments": _serialize_published_assignments(publication),
        "continuities": continuities,
        "manifest": _manifest(period, publication, sources, verified_at),
        "pending_draft_excluded": pending,
    }


# Stable aliases for call sites that describe the same projections differently.
get_periods = list_periods
get_published_schedule = get_published
