"""Freeze a complete published schedule before any export rendering starts."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from datetime import date, timedelta
from types import MappingProxyType
from typing import Any, Mapping

from django.db import connection, transaction

from ros_xolo.programacion.selectors.planning import get_published


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


@dataclass(frozen=True)
class FrozenExportPayload:
    """Detached, recursively immutable input for a single render."""

    payload: Mapping[str, Any]
    manifest: Mapping[str, Any]
    expected_counts: Mapping[str, int]
    expected_ids: Mapping[str, tuple[str, ...]]
    payload_hash: str

    def to_dict(self) -> dict[str, Any]:
        return _thaw(self.payload)

    def manifest_dict(self) -> dict[str, Any]:
        return _thaw(self.manifest)

    def counts_dict(self) -> dict[str, int]:
        return dict(self.expected_counts)

    def ids_dict(self) -> dict[str, list[str]]:
        return {key: list(values) for key, values in self.expected_ids.items()}


def _date_days(date_from, date_to):
    cursor = date_from
    while cursor <= date_to:
        yield cursor
        cursor += timedelta(days=1)


def _schedule_rows(projection: dict[str, Any], day_values: list[str]) -> list[dict[str, Any]]:
    assignments = {}
    for assignment in projection["assignments"]:
        key = (assignment["employee_id"], assignment["start_local"][:10])
        assignments.setdefault(key, []).append(assignment)

    rows = []
    for roster_row in projection["roster"]:
        cells = []
        for day in day_values:
            cells.append(
                {
                    "date": day,
                    "assignments": assignments.get((roster_row["employee_id"], day), []),
                }
            )
        rows.append({**roster_row, "cells": cells})
    return rows


def _expected(projection: dict[str, Any], day_values: list[str]):
    local_breaks = [
        item["break_id"]
        for assignment in projection["assignments"]
        for item in assignment["breaks"]
    ]
    continuity_breaks = [
        item["break_id"]
        for assignment in projection["continuities"]
        for item in assignment["breaks"]
    ]
    continuity_ids = [
        f'{item["origin_publication_id"]}:{item["assignment_id"]}'
        for item in projection["continuities"]
    ]
    counts = {
        "rows": len(projection["roster"]),
        "days": len(day_values),
        "assignments": len(projection["assignments"]),
        "breaks": len(local_breaks),
        "continuities": len(projection["continuities"]),
        "continuity_breaks": len(continuity_breaks),
    }
    ids = {
        "rows": sorted(item["employee_id"] for item in projection["roster"]),
        "days": day_values,
        "assignments": sorted(item["assignment_id"] for item in projection["assignments"]),
        "breaks": sorted(local_breaks),
        "continuities": sorted(continuity_ids),
        "continuity_breaks": sorted(continuity_breaks),
    }
    return counts, ids


def build_export_payload(actor, period_id) -> FrozenExportPayload:
    """Materialize one branch's current local publication and continuity sources.

    PostgreSQL's transaction isolation is raised before the first query in this
    transaction.  Rendering receives only the detached value returned here and
    therefore cannot observe a publication committed later.
    """

    already_atomic = connection.in_atomic_block
    with transaction.atomic():
        if connection.vendor == "postgresql" and not already_atomic:
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        projection = copy.deepcopy(get_published(actor, period_id))

        branch_id = projection["period"]["branch_id"]
        if any(item.get("branch_id") != branch_id for item in projection["assignments"]):
            raise ValueError("La publicación contiene una jornada de otra sucursal.")

        date_from = date.fromisoformat(projection["period"]["date_from"])
        date_to = date.fromisoformat(projection["period"]["date_to"])
        day_values = [day.isoformat() for day in _date_days(date_from, date_to)]
        counts, ids = _expected(projection, day_values)
        payload = {
            **projection,
            "days": day_values,
            "schedule_rows": _schedule_rows(projection, day_values),
            "expected_counts": counts,
            "expected_ids": ids,
        }
        payload_hash = hashlib.sha256(_canonical_json(payload)).hexdigest()
        payload["payload_hash"] = payload_hash
        payload["manifest"] = {
            **payload["manifest"],
            "payload_hash": payload_hash,
            "expected_counts": counts,
        }

    return FrozenExportPayload(
        payload=_freeze(payload),
        manifest=_freeze(payload["manifest"]),
        expected_counts=_freeze(counts),
        expected_ids=_freeze(ids),
        payload_hash=payload_hash,
    )


freeze_export_payload = build_export_payload
