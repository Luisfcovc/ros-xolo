from datetime import date
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from ros_xolo.core.http.errors import error_response
from ros_xolo.core.services.authorization import ActorContext, AuthorizationDenied
from ros_xolo.programacion.selectors.personal import get_personal_schedule

@require_GET
def personal_schedule(request):
    if not request.user.is_authenticated: return error_response("unauthenticated", "Autenticación requerida.")
    if "employee_id" in request.GET: return error_response("validation_error", "employee_id no está permitido.")
    organization_id = request.session.get("organization_id")
    if not organization_id: return error_response("not_found", "No encontrado.")
    try:
        result = get_personal_schedule(ActorContext(request.user.id, organization_id), date.fromisoformat(request.GET["from"]), date.fromisoformat(request.GET["to"]))
        response = JsonResponse(result); response["Cache-Control"] = "private, no-store"; return response
    except (KeyError, ValueError): return error_response("validation_error", "Rango de fechas inválido.")
    except AuthorizationDenied: return error_response("not_found", "No encontrado.")
