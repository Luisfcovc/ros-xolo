"""Playwright renderer for complete, private schedule exports."""

from __future__ import annotations

import hashlib
import html
import os
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from .payload import FrozenExportPayload
from .validation import validate_dom_snapshot, validate_rendered_file


MAX_RENDERERS = 2
RENDER_TIMEOUT_MS = 25_000
PNG_MAX_PIXELS = 60_000_000
PNG_MAX_DIMENSION = 30_000
PNG_VIEWPORT_WIDTH = 1600

_render_slots = threading.BoundedSemaphore(MAX_RENDERERS)


class ExportRenderError(RuntimeError):
    code = "export_failed"


class ExportBusy(ExportRenderError):
    code = "export_busy"


class ExportTimeout(ExportRenderError):
    code = "export_timeout"


class ExportTooLarge(ExportRenderError):
    code = "export_too_large"


@dataclass(frozen=True)
class RenderResult:
    path: Path
    sha256: str
    byte_size: int
    mime_type: str
    width: int | None = None
    height: int | None = None
    pages: int | None = None


def _browser_options():
    executable = getattr(settings, "EXPORT_CHROMIUM_EXECUTABLE", "")
    # Software compositing is substantially more predictable in the minimal
    # Linux container used by validation and avoids a GPU process starving a
    # full-page capture under constrained CI runners.
    options = {
        "headless": True,
        "args": ["--disable-gpu", "--disable-software-rasterizer", "--disable-dev-shm-usage"],
    }
    if executable:
        options["executable_path"] = executable
    return options


def _dom_snapshot(page):
    return page.evaluate(
        """() => {
          const values = selector => [...document.querySelectorAll(selector)]
            .map(node => node.dataset.exportId);
          return {
            counts: {
              rows: document.querySelectorAll('[data-export-kind="rows"]').length,
              days: document.querySelectorAll('[data-export-kind="days"]').length,
              assignments: document.querySelectorAll('[data-export-kind="assignments"]').length,
              breaks: document.querySelectorAll('[data-export-kind="breaks"]').length,
              continuities: document.querySelectorAll('[data-export-kind="continuities"]').length,
              continuity_breaks: document.querySelectorAll('[data-export-kind="continuity_breaks"]').length,
            },
            ids: {
              rows: values('[data-export-kind="rows"]'),
              days: values('[data-export-kind="days"]'),
              assignments: values('[data-export-kind="assignments"]'),
              breaks: values('[data-export-kind="breaks"]'),
              continuities: values('[data-export-kind="continuities"]'),
              continuity_breaks: values('[data-export-kind="continuity_breaks"]'),
            },
          };
        }"""
    )


def _layout_size(page):
    return page.evaluate(
        """() => ({
          width: Math.ceil(document.documentElement.scrollWidth),
          height: Math.ceil(document.documentElement.scrollHeight),
        })"""
    )


def _preflight_png(size):
    width, height = size["width"], size["height"]
    if (
        width <= 0
        or height <= 0
        or width > PNG_MAX_DIMENSION
        or height > PNG_MAX_DIMENSION
        or width * height > PNG_MAX_PIXELS
    ):
        raise ExportTooLarge("El PNG completo excede el límite; solicita el PDF.")


def _pdf_header(frozen: FrozenExportPayload) -> str:
    period = frozen.to_dict()["period"]
    publication = frozen.to_dict()["publication"]
    return (
        '<div style="width:100%;font:10pt Arial,sans-serif;color:#17211b;padding:0 12mm;">'
        f'<strong>{html.escape(period["branch_label"])}</strong> · '
        f'{html.escape(period["date_from"])}–{html.escape(period["date_to"])} · '
        f'v{html.escape(str(publication["version"]))}'
        '</div>'
    )


def _pdf_footer() -> str:
    return (
        '<div style="width:100%;font:10pt Arial,sans-serif;color:#17211b;text-align:center;">'
        'Copia estática. Consulta la versión vigente en ROS-XOLO · página '
        '<span class="pageNumber"></span> de <span class="totalPages"></span>'
        '</div>'
    )


def render_export(frozen: FrozenExportPayload, export_format: str, destination) -> RenderResult:
    """Render to a sibling temporary file, validate it, then publish atomically."""

    if export_format not in {"png", "pdf"}:
        raise ExportRenderError("Formato de exportación inválido.")
    if not _render_slots.acquire(blocking=False):
        raise ExportBusy("El renderizador está ocupado; intenta nuevamente.")

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.stem}-", suffix=f".{export_format}.tmp", dir=destination.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        html = render_to_string(
            "programacion/export.html",
            {"export": frozen.to_dict(), "export_format": export_format},
        )
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(**_browser_options())
            try:
                page = browser.new_page(
                    viewport={"width": PNG_VIEWPORT_WIDTH, "height": 900},
                    device_scale_factor=1,
                )
                page.set_default_timeout(RENDER_TIMEOUT_MS)
                render_started = time.monotonic()
                page.set_content(html, wait_until="load", timeout=RENDER_TIMEOUT_MS)
                page.evaluate("() => document.fonts.ready")
                snapshot = _dom_snapshot(page)
                validate_dom_snapshot(
                    snapshot, frozen.counts_dict(), frozen.ids_dict()
                )
                if export_format == "png":
                    size = _layout_size(page)
                    _preflight_png(size)
                    page.screenshot(
                        path=str(temporary), full_page=True, type="png", timeout=RENDER_TIMEOUT_MS
                    )
                    metadata = validate_rendered_file(
                        temporary,
                        "png",
                        expected_width=size["width"],
                        expected_height=size["height"],
                        max_pixels=PNG_MAX_PIXELS,
                        max_dimension=PNG_MAX_DIMENSION,
                    )
                else:
                    page.emulate_media(media="print")
                    page.pdf(
                        path=str(temporary),
                        format="A4",
                        landscape=True,
                        print_background=True,
                        prefer_css_page_size=False,
                        display_header_footer=True,
                        header_template=_pdf_header(frozen),
                        footer_template=_pdf_footer(),
                        margin={"top": "28mm", "bottom": "18mm", "left": "12mm", "right": "12mm"},
                    )
                    metadata = validate_rendered_file(temporary, "pdf")
                if (time.monotonic() - render_started) * 1000 > RENDER_TIMEOUT_MS:
                    raise ExportTimeout("La exportación excedió 25 segundos.")
            finally:
                browser.close()
        os.replace(temporary, destination)
        sha256 = hashlib.sha256(destination.read_bytes()).hexdigest()
        return RenderResult(
            path=destination,
            sha256=sha256,
            byte_size=metadata["byte_size"],
            mime_type=metadata["mime_type"],
            width=metadata.get("width"),
            height=metadata.get("height"),
            pages=metadata.get("pages"),
        )
    except PlaywrightTimeoutError as exc:
        raise ExportTimeout("La exportación excedió 25 segundos.") from exc
    except ExportRenderError:
        raise
    except Exception as exc:
        raise ExportRenderError("No se pudo generar una exportación completa.") from exc
    finally:
        temporary.unlink(missing_ok=True)
        _render_slots.release()
