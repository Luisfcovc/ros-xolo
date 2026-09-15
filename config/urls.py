from django.contrib.auth.views import LogoutView
from django.conf import settings
from django.urls import include, path
from django.views.static import serve
from ros_xolo.core.views import OrganizationLoginView, home

urlpatterns = [
    path("", home, name="home"),
    path("login/", OrganizationLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("", include("ros_xolo.programacion.urls")),
    path("static/<path:path>", serve, {"document_root": settings.STATIC_ROOT}),
]
