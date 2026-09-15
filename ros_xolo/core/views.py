"""Browser entry points and session-scoped organization selection."""

from django.contrib.auth.views import LoginView
from django.shortcuts import redirect

from ros_xolo.core.models import PermisoPlaneacion, UsuarioOrganizacion


def organization_ids_for(user):
    """Return only organizations in which the user has an active application role."""
    memberships = UsuarioOrganizacion.objects.filter(
        user=user, active=True
    ).values_list("organization_id", flat=True)
    planner_grants = PermisoPlaneacion.objects.filter(
        user=user, enabled=True, branch__active=True
    ).values_list("organization_id", flat=True)
    return sorted(set(memberships) | set(planner_grants), key=str)


class OrganizationLoginView(LoginView):
    """Authenticate and bind the session to the user's sole active organization."""

    template_name = "registration/login.html"

    def form_valid(self, form):
        organizations = organization_ids_for(form.get_user())
        if len(organizations) != 1:
            form.add_error(
                None,
                "Tu cuenta no tiene una organización activa única. Contacta al administrador.",
            )
            return self.form_invalid(form)
        self.request.session["organization_id"] = str(organizations[0])
        return super().form_valid(form)


def home(request):
    """Keep the root URL useful without exposing a planning page anonymously."""
    return redirect("/planning/" if request.user.is_authenticated else "/login/")
