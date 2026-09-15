from dataclasses import dataclass
from django.http import Http404
from ros_xolo.core.models import Empleado, PermisoPlaneacion, UsuarioOrganizacion


class AuthorizationDenied(Http404):
    """Deliberately indistinguishable from a non-existent scoped resource."""


@dataclass(frozen=True)
class ActorContext:
    user_id: int
    organization_id: object


def resolve_employee(actor: ActorContext) -> Empleado:
    try:
        link = UsuarioOrganizacion.objects.select_related("employee").get(user_id=actor.user_id, organization_id=actor.organization_id, active=True, employee__isnull=False)
    except UsuarioOrganizacion.DoesNotExist as exc:
        raise AuthorizationDenied("Identidad personal no disponible.") from exc
    return link.employee


def authorize_planner(actor: ActorContext, branch_id):
    try:
        return PermisoPlaneacion.objects.select_related("branch").get(user_id=actor.user_id, organization_id=actor.organization_id, branch_id=branch_id, enabled=True, branch__active=True)
    except PermisoPlaneacion.DoesNotExist as exc:
        raise AuthorizationDenied("Sucursal no accesible.") from exc
