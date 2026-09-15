from django.apps import AppConfig

class ProgramacionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ros_xolo.programacion"

    def ready(self):
        from ros_xolo.programacion.events import core_changes  # noqa: F401
