import json
from pathlib import Path
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from ros_xolo.core.services.authorization import ActorContext
from ros_xolo.core.services.catalog_changes import apply_core_changes, validate_manifest


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--input", required=True)
        parser.add_argument("--actor", required=True)
        parser.add_argument("--validate-only", action="store_true")

    def handle(self, *args, **options):
        try:
            manifest = validate_manifest(json.loads(Path(options["input"]).read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise CommandError(f"Manifest inválido: {exc}") from exc
        user = get_user_model().objects.filter(username=options["actor"], is_active=True, is_superuser=True).first()
        if not user: raise CommandError("El actor debe ser un administrador activo.")
        if options["validate_only"]:
            self.stdout.write(self.style.SUCCESS("Manifest válido; no se aplicaron cambios.")); return
        revision = apply_core_changes(ActorContext(user.id, manifest["organization_id"]), manifest, manifest.get("expected_core_revision", 0))
        self.stdout.write(self.style.SUCCESS(f"Cambios aplicados; core_revision={revision}."))
