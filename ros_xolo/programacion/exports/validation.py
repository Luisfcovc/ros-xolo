"""Completeness and file-type checks for generated schedule exports."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from pypdf import PdfReader


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PDF_SIGNATURE = b"%PDF-"


class ExportValidationError(ValueError):
    code = "export_failed"


def validate_dom_snapshot(snapshot, expected_counts, expected_ids) -> None:
    """Require exact element counts and stable IDs before capturing the page."""

    for key, expected in expected_counts.items():
        actual = snapshot.get("counts", {}).get(key)
        if actual != expected:
            raise ExportValidationError(
                f"DOM incompleto para {key}: esperado {expected}, obtenido {actual}."
            )
    for key, expected in expected_ids.items():
        actual = sorted(snapshot.get("ids", {}).get(key, []))
        if actual != sorted(expected):
            raise ExportValidationError(f"IDs del DOM no coinciden para {key}.")


def validate_png(path, *, expected_width=None, expected_height=None, max_pixels=60_000_000,
                 max_dimension=30_000):
    file_path = Path(path)
    data = file_path.read_bytes()
    if not data.startswith(PNG_SIGNATURE) or len(data) <= len(PNG_SIGNATURE):
        raise ExportValidationError("El archivo generado no es un PNG válido.")
    try:
        with Image.open(file_path) as image:
            image.verify()
        with Image.open(file_path) as image:
            width, height = image.size
            if image.format != "PNG":
                raise ExportValidationError("El tipo real del archivo no es PNG.")
    except ExportValidationError:
        raise
    except Exception as exc:
        raise ExportValidationError("No se pudo verificar la estructura PNG.") from exc
    if width > max_dimension or height > max_dimension or width * height > max_pixels:
        raise ExportValidationError("Las dimensiones PNG exceden el límite permitido.")
    if expected_width is not None and width != expected_width:
        raise ExportValidationError("El ancho PNG no coincide con el layout verificado.")
    if expected_height is not None and height != expected_height:
        raise ExportValidationError("La altura PNG no coincide con el layout verificado.")
    return {"mime_type": "image/png", "width": width, "height": height, "byte_size": len(data)}


def validate_pdf(path):
    file_path = Path(path)
    data = file_path.read_bytes()
    if not data.startswith(PDF_SIGNATURE) or len(data) <= len(PDF_SIGNATURE):
        raise ExportValidationError("El archivo generado no es un PDF válido.")
    try:
        reader = PdfReader(file_path)
        pages = len(reader.pages)
        if pages < 1:
            raise ExportValidationError("El PDF no contiene páginas.")
        for page in reader.pages:
            if page.mediabox.width <= 0 or page.mediabox.height <= 0:
                raise ExportValidationError("El PDF contiene una página sin dimensiones.")
    except ExportValidationError:
        raise
    except Exception as exc:
        raise ExportValidationError("No se pudo verificar la estructura PDF.") from exc
    return {"mime_type": "application/pdf", "pages": pages, "byte_size": len(data)}


def validate_rendered_file(path, export_format, **dimensions):
    if export_format == "png":
        return validate_png(path, **dimensions)
    if export_format == "pdf":
        return validate_pdf(path)
    raise ExportValidationError("Formato de exportación desconocido.")
