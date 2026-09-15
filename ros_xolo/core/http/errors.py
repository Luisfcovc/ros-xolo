from django.http import JsonResponse

STATUS_FOR_CODE = {
    "unauthenticated": 401,
    "authentication_required": 401,
    "forbidden": 403,
    "permission_denied": 403,
    "not_found": 404,
    "overlap": 409,
    "period_overlap": 409,
    "not_published": 409,
    "employee_ineligible_future": 409,
    "write_busy": 503,
    "stale_base": 412,
    "precondition_required": 428,
    "validation_error": 422,
    "invalid_request": 400,
    "invalid_interval": 422,
    "invalid_break": 422,
    "invalid_reference": 422,
    "export_too_large": 422,
    "export_expired": 410,
    "export_busy": 503,
    "export_failed": 503,
    "export_timeout": 503,
}


def error_response(code, message=None, *, restricted=False, fields=None, action=None, conflicts=None):
    body = {"error": {"code": code, "message": "No se puede completar la operación." if restricted else (message or code)}}
    if action:
        body["error"]["action"] = action
    if fields and not restricted:
        body["error"]["fields"] = fields
    if conflicts and not restricted:
        body["error"]["conflicts"] = conflicts
    return JsonResponse(body, status=STATUS_FOR_CODE.get(code, 400))
