"""Standalone Windows entry point for the distribution report server."""

from __future__ import annotations

import sys
import socket
import threading
import webbrowser
from pathlib import Path

from distribution_signal_verifier.live_report_server import _load_local_config, main as server_main


def _application_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _bundled_template() -> Path | None:
    """Return the HTML template bundled by PyInstaller, when available."""
    if not getattr(sys, "frozen", False):
        return None
    extraction_root = getattr(sys, "_MEIPASS", None)
    if not extraction_root:
        return None
    template_path = Path(extraction_root) / "distribution_report.html"
    return template_path if template_path.is_file() else None


def _port_available(host: str, port: int) -> bool:
    probe_host = "" if host in {"0.0.0.0", "::"} else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((probe_host, port))
        except OSError:
            return False
    return True


def main() -> int:
    root = _application_root()
    local_config = _load_local_config()
    server_config = local_config.get("server", {})
    if not isinstance(server_config, dict):
        server_config = {}
    args = list(sys.argv[1:])
    explicit_port = "--port" in args
    if "--template" not in args:
        template_path = _bundled_template()
        if template_path is None:
            template_value = server_config.get("template") or "distribution_report.html"
            template_path = Path(str(template_value))
            if not template_path.is_absolute():
                template_path = root / template_path
        args.extend(["--template", str(template_path)])
    if "--host" not in args:
        args.extend(["--host", str(server_config.get("host") or "0.0.0.0")])
    if "--port" not in args:
        args.extend(["--port", str(server_config.get("port") or 8899)])
    host = "127.0.0.1"
    port = "8899"
    if "--port" in args:
        port = args[args.index("--port") + 1]
    if "--host" in args:
        host = args[args.index("--host") + 1]

    if not explicit_port:
        try:
            configured_port = int(port)
        except ValueError:
            configured_port = 8899
        selected_port = configured_port
        while selected_port < configured_port + 20 and not _port_available(host, selected_port):
            selected_port += 1
        if selected_port != configured_port:
            args[args.index("--port") + 1] = str(selected_port)
            port = str(selected_port)
            print(
                f"Port {configured_port} is already in use; using port {selected_port} for this report."
            )

    sys.argv = [sys.argv[0], *args]
    browser_host = host if host not in {"0.0.0.0", "::"} else "127.0.0.1"
    browser_url = f"http://{browser_host}:{port}/?network=distribution"
    browser_timer = threading.Timer(1.0, webbrowser.open, args=(browser_url,))
    browser_timer.daemon = True
    browser_timer.start()
    return server_main()


if __name__ == "__main__":
    raise SystemExit(main())