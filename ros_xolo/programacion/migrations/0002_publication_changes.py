import django.db.models.deletion
import uuid

from django.db import migrations, models


SNAPSHOT_TABLES = (
    "programacion_publicacionprogramacion",
    "programacion_filaempleadopublicada",
    "programacion_jornadapublicada",
    "programacion_descansopublicado",
    "programacion_cambiopublicacion",
)


def protect_snapshots(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE OR REPLACE FUNCTION programacion_reject_snapshot_mutation()
            RETURNS trigger AS $$
            BEGIN
              RAISE EXCEPTION 'published schedule snapshots are append-only';
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        for table in SNAPSHOT_TABLES:
            cursor.execute(
                f"CREATE TRIGGER {table}_append_only "
                f"BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW "
                "EXECUTE FUNCTION programacion_reject_snapshot_mutation();"
            )
            cursor.execute(f"REVOKE UPDATE, DELETE ON {table} FROM PUBLIC;")


def unprotect_snapshots(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        for table in SNAPSHOT_TABLES:
            cursor.execute(f"DROP TRIGGER IF EXISTS {table}_append_only ON {table};")
        cursor.execute("DROP FUNCTION IF EXISTS programacion_reject_snapshot_mutation();")


class Migration(migrations.Migration):
    dependencies = [("programacion", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="CambioPublicacion",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("kind", models.CharField(choices=[("assignment_added", "Jornada añadida"), ("assignment_modified", "Jornada modificada"), ("assignment_removed", "Jornada retirada"), ("roster_added", "Fila añadida"), ("roster_removed", "Fila retirada"), ("roster_modified", "Fila modificada")], max_length=32)),
                ("before", models.JSONField(blank=True, null=True)),
                ("after", models.JSONField(blank=True, null=True)),
                ("changed_fields", models.JSONField(default=list)),
                ("assignment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="core.asignacion")),
                ("employee", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="core.empleado")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="core.organizacion")),
                ("publication", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="changes", to="programacion.publicacionprogramacion")),
            ],
        ),
        migrations.AddIndex(
            model_name="cambiopublicacion",
            index=models.Index(fields=["publication", "kind", "id"], name="programacio_public_07cb0f_idx"),
        ),
        migrations.AddConstraint(
            model_name="cambiopublicacion",
            constraint=models.CheckConstraint(condition=models.Q(("before__isnull", False), ("after__isnull", False), _connector="OR"), name="schedule_change_has_content"),
        ),
        migrations.RunPython(protect_snapshots, unprotect_snapshots),
    ]
