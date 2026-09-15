"""Render both private formats and create reviewable, machine-readable evidence."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ros_xolo.core.models import Organizacion
from ros_xolo.core.services.authorization import ActorContext
from ros_xolo.programacion.models import PeriodoProgramacion
from ros_xolo.programacion.services.exports import get_export_file, request_export
from ros_xolo.programacion.exports.validation import validate_pdf, validate_png


class Command(BaseCommand):
    help = "Genera y verifica exportaciones PNG/PDF del escenario publicado indicado."

    def add_arguments(self, parser):
        parser.add_argument("--scenario", default="reference-week")
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--planner", default="demo.planner.all")

    def handle(self, *args, **options):
        if options["scenario"] != "reference-week":
            raise CommandError("Solo está definido el escenario reference-week.")
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.filter(username=options["planner"]).first()
        org = Organizacion.objects.filter(name="DEMO: XOLO").first()
        if not user or not org:
            raise CommandError("Ejecuta seed_demo antes de validar exportaciones.")
        period = PeriodoProgramacion.objects.filter(organization=org, current_publication_id__isnull=False).order_by("date_from").first()
        if not period:
            raise CommandError("No existe una reference-week publicada.")
        output = Path(options["output_dir"]).resolve()
        output.mkdir(parents=True, exist_ok=True)
        for page_image in output.glob("reference-week-page-*.png"):
            page_image.unlink()
        actor = ActorContext(user_id=user.id, organization_id=org.id)
        report = {"scenario": options["scenario"], "period_id": str(period.id), "formats": {}}
        for export_format in ("png", "pdf"):
            export = request_export(actor, period.id, export_format)
            _, source = get_export_file(actor, export.id)
            target = output / f"reference-week.{export_format}"
            shutil.copy2(source, target)
            details = validate_png(target) if export_format == "png" else validate_pdf(target)
            details.update({"sha256": export.content_hash, "manifest": export.manifest, "expected_counts": export.expected_counts})
            if export_format == "pdf":
                renderer = shutil.which("pdftoppm")
                if not renderer:
                    raise CommandError("pdftoppm es obligatorio para revisar todas las páginas PDF.")
                prefix = output / "reference-week-page"
                subprocess.run([renderer, "-png", str(target), str(prefix)], check=True)
                details["page_images"] = sorted(path.name for path in output.glob("reference-week-page-*.png"))
                if len(details["page_images"]) != details["pages"]:
                    raise CommandError("No se pudieron renderizar todas las páginas del PDF.")
            report["formats"][export_format] = details
        (output / "validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Exportaciones verificadas en {output}"))
