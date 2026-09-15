import json
from datetime import date
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from ros_xolo.core.http.errors import error_response
from ros_xolo.core.selectors.catalogs import get_planning_catalogs, resolve_shift
from ros_xolo.core.services.authorization import ActorContext, AuthorizationDenied
from ros_xolo.core.services.locking import WriteBusy
from ros_xolo.core.models import PermisoPlaneacion
from ros_xolo.programacion.selectors.planning import NotPublished, get_draft, get_published, list_periods
from ros_xolo.programacion.services.drafts import PreconditionRequired, StaleBase, replace_draft
from ros_xolo.programacion.services.periods import PeriodOverlap, create_period
from ros_xolo.programacion.services.publication import EmployeeIneligibleFuture, publish_period
from ros_xolo.programacion.services.conflicts import OverlapConflict
from ros_xolo.programacion.services.validation import ScheduleValidationError


def _actor(request):
    if not request.user.is_authenticated: return None
    organization_id = request.session.get("organization_id")
    return ActorContext(request.user.id, organization_id) if organization_id else None
def _body(request): return json.loads(request.body or "{}")
def _json(data, status=200, etag=None):
    response = JsonResponse(data, status=status)
    response["Cache-Control"] = "private, no-store"
    if etag: response["ETag"] = etag
    return response

@require_http_methods(["GET"])
def branches(request):
    actor = _actor(request)
    if not actor: return error_response("unauthenticated", "Autenticación requerida.")
    values = PermisoPlaneacion.objects.filter(user_id=actor.user_id, organization_id=actor.organization_id, enabled=True, branch__active=True).select_related("branch")
    return _json({"branches": [{"id": str(row.branch_id), "name": row.branch.name, "timezone": row.branch.timezone} for row in values]})

@require_http_methods(["GET"])
def catalogs(request, branch_id):
    actor = _actor(request)
    if not actor: return error_response("unauthenticated", "Autenticación requerida.")
    try:
        catalog = get_planning_catalogs(actor, branch_id)
        return _json({"core_revision": catalog["core_revision"], "employees": [{"id": str(item.employee.id), "label": item.employee.display_name} for item in catalog["employees"]], "roles": [{"id": str(item.id), "label": item.name} for item in catalog["roles"]], "shifts": [{"id": str(item.id), "label": item.name} for item in catalog["shifts"]]})
    except AuthorizationDenied: return error_response("not_found", "No encontrado.")

@require_http_methods(["POST"])
def resolve_shift_view(request, period_id):
    actor = _actor(request)
    if not actor: return error_response("unauthenticated", "Autenticación requerida.")
    try:
        payload = _body(request); draft_state = get_draft(actor, period_id)
        outcome = resolve_shift(actor, draft_state["period"]["branch_id"], payload["shift_id"], date.fromisoformat(payload["start_date"]), payload.get("start_offset"), payload.get("end_offset"))
        return _json({"starts_at": outcome["starts_at"].isoformat(), "ends_at": outcome["ends_at"].isoformat(), "shift_id": str(outcome["shift"].id)})
    except (KeyError, ValueError, json.JSONDecodeError): return error_response("validation_error", "No se pudo resolver el turno.")
    except AuthorizationDenied: return error_response("not_found", "No encontrado.")

@require_http_methods(["GET", "POST"])
def periods(request):
    actor = _actor(request)
    if not actor: return error_response("unauthenticated", "Autenticación requerida.")
    try:
        if request.method == "GET":
            branch_id = request.GET["branch_id"]; start = request.GET.get("from"); end = request.GET.get("to")
            return _json({"periods": list_periods(actor, branch_id, date.fromisoformat(start) if start else None, date.fromisoformat(end) if end else None)})
        payload = _body(request); period, _, _ = create_period(actor, payload["branch_id"], date.fromisoformat(payload["date_from"]), date.fromisoformat(payload["date_to"]))
        draft = get_draft(actor, period.id); response = _json(draft, 201, draft["etag"]); response["Location"] = f"/api/v1/planning/periods/{period.id}/draft"; return response
    except (KeyError, ValueError, json.JSONDecodeError): return error_response("validation_error", "Solicitud inválida.")
    except PeriodOverlap: return error_response("period_overlap", "El periodo se traslapa.")
    except AuthorizationDenied: return error_response("not_found", "No encontrado.")
    except WriteBusy: return error_response("write_busy", "Intenta nuevamente.")

@require_http_methods(["GET", "PUT"])
def draft(request, period_id):
    actor = _actor(request)
    if not actor: return error_response("unauthenticated", "Autenticación requerida.")
    try:
        if request.method == "GET":
            result = get_draft(actor, period_id); return _json(result, etag=result["etag"])
        write_result = replace_draft(
            actor, period_id, request.headers.get("If-Match"), _body(request)
        )
        result = get_draft(actor, period_id)
        result["saved"] = write_result["saved"]
        return _json(result, etag=result["etag"])
    except PreconditionRequired: return error_response("precondition_required", "If-Match es obligatorio.")
    except StaleBase: return error_response("stale_base", "Refresca antes de guardar.")
    except AuthorizationDenied: return error_response("not_found", "No encontrado.")
    except OverlapConflict as exc:
        return error_response(
            "overlap", str(exc), fields=exc.fields, action=exc.action, conflicts=exc.conflicts
        )
    except ScheduleValidationError as exc:
        return error_response(exc.code, str(exc), fields=exc.fields)

@require_http_methods(["POST"])
def publish(request, period_id):
    actor = _actor(request)
    if not actor: return error_response("unauthenticated", "Autenticación requerida.")
    try:
        result = publish_period(actor, period_id, request.headers.get("If-Match"))
        body = {
            "outcome": result["outcome"],
            "publication_id": str(result["publication_id"]),
            "version": result["version"],
            "previous_version": result["previous_version"],
            "published_at": result["published_at"].isoformat(),
            "changes": result["changes"],
        }
        return _json(body, 200 if result["outcome"] == "no_changes" else 201, result["etag"])
    except PreconditionRequired: return error_response("precondition_required", "If-Match es obligatorio.")
    except StaleBase: return error_response("stale_base", "Refresca antes de publicar.")
    except OverlapConflict as exc:
        return error_response(
            "overlap", str(exc), fields=exc.fields, action=exc.action, conflicts=exc.conflicts
        )
    except AuthorizationDenied: return error_response("not_found", "No encontrado.")
    except EmployeeIneligibleFuture as exc:
        return error_response(
            exc.code, str(exc), fields=exc.fields, action=exc.action
        )
    except ScheduleValidationError as exc:
        return error_response(exc.code, str(exc), fields=exc.fields)

@require_http_methods(["GET"])
def published(request, period_id):
    actor = _actor(request)
    if not actor: return error_response("unauthenticated", "Autenticación requerida.")
    try: return _json(get_published(actor, period_id))
    except NotPublished: return error_response("not_published", "Aún no hay publicación.")
    except AuthorizationDenied: return error_response("not_found", "No encontrado.")
