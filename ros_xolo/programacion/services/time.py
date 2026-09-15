from datetime import datetime
from zoneinfo import ZoneInfo


class LocalTimeError(ValueError): pass


def parse_rfc3339(value):
    if not isinstance(value, str): raise LocalTimeError("Datetime requerido.")
    try: result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc: raise LocalTimeError("RFC 3339 inválido.") from exc
    if result.tzinfo is None: raise LocalTimeError("El offset es obligatorio.")
    return result


def local_snapshot(value, timezone_name):
    instant = parse_rfc3339(value) if isinstance(value, str) else value
    if instant.tzinfo is None: raise LocalTimeError("El offset es obligatorio.")
    local = instant.astimezone(ZoneInfo(timezone_name))
    return {"utc": instant.astimezone(ZoneInfo("UTC")), "local": local, "offset": int(local.utcoffset().total_seconds()), "timezone": timezone_name}


def parse_period_datetime(value, timezone_name):
    snapshot = local_snapshot(value, timezone_name)
    supplied = parse_rfc3339(value)
    expected = snapshot["utc"].astimezone(ZoneInfo(timezone_name))
    if expected.utcoffset() != supplied.utcoffset(): raise LocalTimeError("Offset incompatible con la zona del periodo.")
    return snapshot
