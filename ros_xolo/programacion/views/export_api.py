"""Private HTTP contract for synchronous schedule exports."""

from __future__ import annotations

import json

from django.core.exceptions import ObjectDoesNotExist
from django.http import FileResponse, JsonResponse
from django.views.decorators.http import require_GET, require_POST

from ros_xolo.core.http.errors import error_response
from ros_xolo.core.services.authorization import ActorContext, AuthorizationDenied
from ros_xolo.programacion.exports.renderer import ExportRenderError
from ros_xolo.programacion.selectors.planning import NotPublished
from ros_xolo.programacion.services.exports import (
    ExportExpired,
    ExportUnavailable,
    InvalidExportFormat,
    export_metadata,
    get_export,
    get_export_file,
    request_export,
)


def _actor(request):
    organization_id = request.session.get("organization_id")
    if not request.user.is_authenticated or not organization_id:
        return None
    return ActorContext(request.user.id, organization_id)


def _json(data, status=200):
    response = JsonResponse(data, status=status)
    response["Cache-Control"] = "private, no-store"
    return response


@require_POST
def create_export(request, period_id):
    actor = _actor(request)
    if not actor:
        return error_response("authentication_required", "Autenticación requerida.")
    try:
        payload = json.loads(request.body or "{}")
        if not isinstance(payload, dict) or set(payload) != {"format"}:
            raise InvalidExportFormat("La solicitud solo admite format.")
        export = request_export(actor, period_id, payload["format"])
        return _json(export_metadata(export), status=201)
    except (json.JSONDecodeError, KeyError, InvalidExportFormat) as exc:
        return error_response("invalid_request", str(exc) or "Solicitud inválida.")
    except NotPublished:
        return error_response("not_published", "Publica el periodo antes de exportar.")
    except (AuthorizationDenied, ObjectDoesNotExist):
        return error_response("not_found", "No encontrado.")
    except ExportRenderError as exc:
        return error_response(exc.code, str(exc))


@require_GET
def export_status(request, export_id):
    actor = _actor(request)
    if not actor:
        return error_response("authentication_required", "Autenticación requerida.")
    try:
        export = get_export(actor, export_id)
        if export.status == export.EXPIRED:
            return error_response("export_expired", "La exportación venció.")
        return _json(export_metadata(export))
    except (AuthorizationDenied, ObjectDoesNotExist):
        return error_response("not_found", "No encontrado.")


@require_GET
def export_file(request, export_id):
    actor = _actor(request)
    if not actor:
        return error_response("authentication_required", "Autenticación requerida.")
    try:
        export, path = get_export_file(actor, export_id)
        mime_type = "image/png" if export.format == export.PNG else "application/pdf"
        version = export.manifest.get("sources", [{}])[0].get("version", "publicada")
        filename = f"programacion-{export.period_id}-v{version}.{export.format}"
        response = FileResponse(path.open("rb"), content_type=mime_type, as_attachment=True, filename=filename)
        response["Cache-Control"] = "private, no-store"
        response["Content-Length"] = str(export.byte_size)
        return response
    except ExportExpired:
        return error_response("export_expired", "La exportación venció.")
    except ExportUnavailable as exc:
        return error_response("export_failed", str(exc))
    except (AuthorizationDenied, ObjectDoesNotExist):
        return error_response("not_found", "No encontrado.")
