"""Desktop entry point for the local pywebview shell."""

from __future__ import annotations

import mimetypes
import sys
from collections.abc import Callable
from pathlib import Path
from urllib.parse import unquote

from frivault.bridge.api import AppApi
from frivault.logging_config import configure_logging
from frivault.resources import resource_path
from frivault.settings import SettingsStore

_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; "
    "connect-src 'self'; object-src 'none'; frame-src 'none'; "
    "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)


class LocalUi:
    """Serve only bundled UI files through pywebview's local WSGI server."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def __call__(self, environ: dict[str, object], start_response: Callable) -> list[bytes]:
        method = environ.get("REQUEST_METHOD", "GET")
        if method not in ("GET", "HEAD"):
            return self._respond(start_response, "405 Method Not Allowed", b"", "text/plain")

        raw_path = str(environ.get("PATH_INFO", "/"))
        requested = unquote(raw_path).lstrip("/") or "index.html"
        candidate = (self._root / requested).resolve()
        if self._root not in candidate.parents or not candidate.is_file():
            return self._respond(start_response, "404 Not Found", b"Not found", "text/plain")

        body = candidate.read_bytes()
        media_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        return self._respond(
            start_response,
            "200 OK",
            body if method == "GET" else b"",
            media_type,
            content_length=len(body),
        )

    @staticmethod
    def _respond(
        start_response: Callable,
        status: str,
        body: bytes,
        media_type: str,
        *,
        content_length: int | None = None,
    ) -> list[bytes]:
        headers = [
            ("Content-Type", media_type),
            ("Content-Security-Policy", _CSP),
            ("X-Content-Type-Options", "nosniff"),
            ("Cache-Control", "no-store"),
            ("Content-Length", str(len(body) if content_length is None else content_length)),
        ]
        start_response(status, headers)
        return [body]


def main() -> None:
    """Start Frivault's local desktop window."""

    logger = configure_logging()
    SettingsStore().load()
    logger.info("app_started")

    try:
        import webview
    except ImportError as exc:
        raise SystemExit(
            "Frivault needs its desktop dependency. From the project folder run: "
            "python -m pip install -e ."
        ) from exc

    if not _webview2_runtime_version():
        message = (
            "Frivault needs the Microsoft Edge WebView2 Runtime. Install the Evergreen Runtime "
            "from https://developer.microsoft.com/microsoft-edge/webview2/ and reopen Frivault."
        )
        logger.error("webview2_runtime_missing")
        if sys.platform == "win32":
            import ctypes

            ctypes.windll.user32.MessageBoxW(None, message, "Frivault", 0x10)
        else:
            raise SystemExit(message)
        return

    ui_root = resource_path("ui")
    index_file = ui_root / "index.html"
    if not index_file.is_file():
        raise SystemExit(f"Frivault UI assets are missing: {index_file}")

    api = AppApi()
    window = webview.create_window(
        "Frivault",
        LocalUi(ui_root),
        js_api=api,
        width=1180,
        height=780,
        min_size=(820, 560),
        background_color="#0D1712",
        text_select=True,
    )
    api._attach_window(window)

    def lock_on_close() -> bool:
        return api._shutdown()

    window.events.closing += lock_on_close
    webview.start(ssl=True)


def _webview2_runtime_version() -> str | None:
    """Return an installed Evergreen WebView2 Runtime version on Windows."""

    if sys.platform != "win32":
        return "not-applicable"
    import winreg

    product_id = r"Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
    locations = (
        (winreg.HKEY_CURRENT_USER, winreg.KEY_WOW64_64KEY),
        (winreg.HKEY_CURRENT_USER, winreg.KEY_WOW64_32KEY),
        (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_64KEY),
        (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_32KEY),
    )
    for hive, view in locations:
        try:
            with winreg.OpenKey(hive, product_id, 0, winreg.KEY_READ | view) as key:
                version, _ = winreg.QueryValueEx(key, "pv")
        except OSError:
            continue
        if isinstance(version, str) and version.strip() not in {"", "0.0.0.0"}:
            return version.strip()
    return None
