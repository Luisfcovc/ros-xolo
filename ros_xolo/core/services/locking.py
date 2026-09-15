from contextlib import contextmanager
from django.db import OperationalError, connection, transaction
from ros_xolo.core.models import Organizacion


class WriteBusy(Exception): pass


@contextmanager
def organization_lock(organization_id, timeout_seconds=5):
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL lock_timeout = %s", [f"{timeout_seconds}s"])
            organization = Organizacion.objects.select_for_update().get(pk=organization_id)
            yield organization
    except Organizacion.DoesNotExist as exc:
        raise WriteBusy("Organización no disponible para escritura.") from exc
    except OperationalError as exc:
        if "lock timeout" in str(exc).lower() or "canceling statement" in str(exc).lower():
            raise WriteBusy("write_busy") from exc
        raise
