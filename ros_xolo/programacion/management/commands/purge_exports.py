from django.core.management.base import BaseCommand

from ros_xolo.programacion.services.exports import purge_expired_exports


class Command(BaseCommand):
    help = "Elimina archivos privados vencidos y temporales abandonados de exportación."

    def handle(self, *args, **options):
        result = purge_expired_exports()
        self.stdout.write(
            self.style.SUCCESS(
                f"Exportaciones vencidas: {result['expired']}; "
                f"temporales eliminados: {result['temporaries_removed']}."
            )
        )
