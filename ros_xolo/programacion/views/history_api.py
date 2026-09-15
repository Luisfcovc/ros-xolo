from datetime import date

from django.core.exceptions import ObjectDoesNotExist
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from ros_xolo.core.http.errors import error_response
from ros_xolo.core.services.authorization import ActorContext, AuthorizationDenied
from ros_xolo.programacion.selectors.alerts import get_active_alerts
from ros_xolo.programacion.selectors.history import (
    InvalidPagination,
    get_history,
    get_personal_history,
    get_personal_version,
)


def _actor(request):
    organization_id = request.session.get("organization_id")
    if not request.user.is_authenticated or not organization_id:
        return None
    return ActorContext(request.user.id, organization_id)


def _json(data):
    response = JsonResponse(data)
    response["Cache-Control"] = "private, no-store"
    return response


@require_GET
def versions(request, period_id):
    actor = _actor(request)
    if not actor:
        return error_response("authentication_required", "Autenticación requerida.")
    try:
        return _json(
            get_history(
                actor,
                period_id,
                cursor=request.GET.get("cursor"),
                limit=request.GET.get("limit", 50),
            )
        )
    except InvalidPagination as exc:
        return error_response("invalid_request", str(exc))
    except (AuthorizationDenied, ObjectDoesNotExist):
        return error_response("not_found", "No encontrado.")


@require_GET
def version_detail(request, period_id, version):
    actor = _actor(request)
    if not actor:
        return error_response("authentication_required", "Autenticación requerida.")
    try:
        return _json(get_history(actor, period_id, version=version))
    except (AuthorizationDenied, ObjectDoesNotExist, ValueError):
        return error_response("not_found", "No encontrado.")


@require_GET
def personal_history(request):
    actor = _actor(request)
    if not actor:
        return error_response("authentication_required", "Autenticación requerida.")
    try:
        return _json(
            get_personal_history(
                actor,
                date.fromisoformat(request.GET["from"]),
                date.fromisoformat(request.GET["to"]),
                cursor=request.GET.get("cursor"),
                limit=request.GET.get("limit", 50),
            )
        )
    except InvalidPagination as exc:
        return error_response("invalid_request", str(exc))
    except (KeyError, ValueError) as exc:
        return error_response("invalid_request", str(exc))
    except AuthorizationDenied:
        return error_response("not_found", "No encontrado.")


@require_GET
def personal_version(request, period_id, version):
    actor = _actor(request)
    if not actor:
        return error_response("authentication_required", "Autenticación requerida.")
    try:
        return _json(get_personal_version(actor, period_id, version))
    except (ObjectDoesNotExist, AuthorizationDenied):
        return error_response("not_found", "No encontrado.")


@require_GET
def alerts(request):
    actor = _actor(request)
    if not actor:
        return error_response("authentication_required", "Autenticación requerida.")
    try:
        return _json({"alerts": get_active_alerts(actor, request.GET["branch_id"])})
    except (KeyError, ValueError, AuthorizationDenied):
        return error_response("not_found", "No encontrado.")
