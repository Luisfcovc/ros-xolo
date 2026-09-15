"""Collective and privacy-filtered immutable publication history."""

from django.db.models import Q

from ros_xolo.core.services.authorization import authorize_planner, resolve_employee
from ros_xolo.programacion.models import CambioPublicacion, PeriodoProgramacion, PublicacionProgramacion
from ros_xolo.programacion.selectors.planning import (
    _period_dict,
    _publication_dict,
    _published_roster,
    _serialize_published_assignments,
)


class InvalidPagination(ValueError):
    code = "invalid_request"


def _limit(value):
    try:
        value = int(value)
    except (TypeError, ValueError) as exc:
        raise InvalidPagination("limit debe ser entero.") from exc
    if value < 1 or value > 200:
        raise InvalidPagination("limit debe estar entre 1 y 200.")
    return value


def _change(row):
    return {
        "id": str(row.id),
        "publication_id": str(row.publication_id),
        "version": row.publication.version,
        "published_at": row.publication.published_at.isoformat(),
        "publisher_label": row.publication.publisher_label,
        "assignment_id": str(row.assignment_id) if row.assignment_id else None,
        "employee_id": str(row.employee_id) if row.employee_id else None,
        "kind": row.kind,
        "before": row.before,
        "after": row.after,
        "changed_fields": row.changed_fields,
    }


def _load_period(actor, period_id):
    period = PeriodoProgramacion.objects.select_related("branch").get(
        pk=period_id, organization_id=actor.organization_id
    )
    authorize_planner(actor, period.branch_id)
    return period


def get_history(actor, period_id, *, version=None, cursor=None, limit=50):
    period = _load_period(actor, period_id)
    if version is not None:
        publication = PublicacionProgramacion.objects.get(period=period, version=version)
        return {
            "period": _period_dict(period),
            "publication": _publication_dict(
                publication, current=publication.id == period.current_publication_id
            ),
            "is_current": publication.id == period.current_publication_id,
            "roster": _published_roster(publication),
            "assignments": _serialize_published_assignments(publication),
            "changes": [
                _change(row)
                for row in publication.changes.select_related("publication").order_by("kind", "id")
            ],
        }

    limit = _limit(limit)
    publications = PublicacionProgramacion.objects.filter(period=period).order_by("-version")
    if cursor:
        try:
            publications = publications.filter(version__lt=int(cursor))
        except (TypeError, ValueError) as exc:
            raise InvalidPagination("cursor inválido.") from exc
    page = list(publications[: limit + 1])
    has_more = len(page) > limit
    page = page[:limit]
    return {
        "period": _period_dict(period),
        "versions": [
            {
                **_publication_dict(row, current=row.id == period.current_publication_id),
                "is_current": row.id == period.current_publication_id,
                "change_count": row.changes.count(),
            }
            for row in page
        ],
        "next_cursor": str(page[-1].version) if has_more else None,
    }


def _personal_change(row, employee_id):
    employee_id = str(employee_id)
    before_employee = str((row.before or {}).get("employee_id", ""))
    after_employee = str((row.after or {}).get("employee_id", ""))
    if row.kind.startswith("roster_"):
        if str(row.employee_id) != employee_id:
            return None
        return _change(row)
    if before_employee == employee_id and after_employee and after_employee != employee_id:
        result = _change(row)
        result.update(kind="assignment_removed", after=None, employee_id=employee_id)
        return result
    if after_employee == employee_id and before_employee and before_employee != employee_id:
        result = _change(row)
        result.update(kind="assignment_added", before=None, employee_id=employee_id)
        return result
    if before_employee == employee_id or after_employee == employee_id:
        result = _change(row)
        result["employee_id"] = employee_id
        return result
    return None


def get_personal_history(actor, date_from, date_to, *, cursor=None, limit=50):
    employee = resolve_employee(actor)
    limit = _limit(limit)
    rows = (
        CambioPublicacion.objects.filter(
            organization_id=actor.organization_id,
            publication__period__date_to__gte=date_from,
            publication__period__date_from__lte=date_to,
        )
        .filter(
            Q(employee=employee)
            | Q(before__employee_id=str(employee.id))
            | Q(after__employee_id=str(employee.id))
        )
        .select_related("publication", "publication__period")
        .order_by("-publication__published_at", "-id")
    )
    if cursor:
        rows = rows.filter(id__lt=cursor)
    page = list(rows[: limit + 1])
    has_more = len(page) > limit
    projected = [item for row in page[:limit] if (item := _personal_change(row, employee.id))]
    return {
        "range": {"from": date_from.isoformat(), "to": date_to.isoformat()},
        "changes": projected,
        "next_cursor": str(page[limit - 1].id) if has_more else None,
    }


def get_personal_version(actor, period_id, version):
    employee = resolve_employee(actor)
    period = PeriodoProgramacion.objects.get(
        pk=period_id, organization_id=actor.organization_id
    )
    publication = PublicacionProgramacion.objects.get(period=period, version=version)
    assignments = publication.assignments.filter(employee=employee)
    roster = publication.roster.filter(employee=employee)
    change_rows = publication.changes.filter(
        Q(employee=employee)
        | Q(before__employee_id=str(employee.id))
        | Q(after__employee_id=str(employee.id))
    ).select_related("publication")
    projected = [
        item for row in change_rows if (item := _personal_change(row, employee.id))
    ]
    if not assignments.exists() and not roster.exists() and not projected:
        raise PeriodoProgramacion.DoesNotExist
    return {
        "period_id": str(period.id),
        "publication": _publication_dict(
            publication, current=publication.id == period.current_publication_id
        ),
        "assignments": [
            row
            for row in _serialize_published_assignments(publication)
            if row["employee_id"] == str(employee.id)
        ],
        "included_in_roster": roster.exists(),
        "changes": projected,
    }
