"""Explicit loopback server for the read-only MLA console."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Lock

from ..ops.resource_monitor import ResourceReading, sample_local_resources
from .dashboard_page import (
    load_locked_verification_queue, load_project_overview, render_html, render_unavailable,
)
from .status_view import load_snapshot, load_synthetic_evidence


_UNAVAILABLE = (ValueError, OSError, TypeError, KeyError, RecursionError)
_CSS = Path(__file__).with_name("dashboard.css")


def host_allowed(host: str | None, port: int) -> bool:
    return host in (f"127.0.0.1:{port}", f"localhost:{port}")


def origin_allowed(origin: str | None, port: int) -> bool:
    return origin is None or origin in (f"http://127.0.0.1:{port}", f"http://localhost:{port}")


class DashboardHandler(BaseHTTPRequestHandler):
    server: LocalStatusServer
    server_version = "MLA"
    sys_version = ""
    timeout = 5

    def log_message(self, format: str, *args) -> None:
        # Do not log untrusted URLs, queries or headers.
        return

    def _respond(self, status: int, payload: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        if status != 204:
            self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; style-src 'self'; img-src 'self'; frame-ancestors 'none'; "
                         "base-uri 'none'; form-action 'none'")
        if status == 405:
            self.send_header("Allow", "GET, HEAD")
        self.end_headers()
        if self.command != "HEAD" and payload:
            self.wfile.write(payload)

    def _json(self, payload: dict) -> None:
        self._respond(200, json.dumps(payload, sort_keys=True).encode("ascii"),
                      "application/json; charset=utf-8")

    def _serve_read(self) -> None:
        port = self.server.server_address[1]
        hosts = self.headers.get_all("Host", [])
        origins = self.headers.get_all("Origin", [])
        fetch_sites = self.headers.get_all("Sec-Fetch-Site", ["none"])
        if (self.client_address[0] != "127.0.0.1" or len(hosts) != 1
            or not host_allowed(hosts[0], port)
            or (origins and origins != [f"http://{hosts[0]}"])
            or fetch_sites not in (["none"], ["same-origin"])):
            return self._respond(403, b"forbidden", "text/plain; charset=utf-8")
        if self.path == "/dashboard.css":
            return self._respond(200, self.server.stylesheet, "text/css; charset=utf-8")
        if self.path == "/favicon.ico":
            return self._respond(204, b"", "image/x-icon")
        if self.path not in ("/", "/status.json", "/evidence.json"):
            return self._respond(404, b"not found", "text/plain; charset=utf-8")

        root = self.server.project_root
        try:
            snapshot = load_snapshot(root)
        except _UNAVAILABLE:
            if self.path == "/":
                return self._respond(503, render_unavailable(), "text/html; charset=utf-8")
            return self._respond(503, b"status unavailable", "text/plain; charset=utf-8")
        if self.path == "/status.json":
            return self._json(snapshot.to_public_dict())

        try:
            evidence = load_synthetic_evidence(root)
        except _UNAVAILABLE:
            evidence = None
        if self.path == "/evidence.json":
            if evidence is None:
                return self._respond(503, b"evidence unavailable", "text/plain; charset=utf-8")
            return self._json(evidence.to_public_dict())

        try:
            project = load_project_overview(root)
        except _UNAVAILABLE:
            project = None
        try:
            gates = load_locked_verification_queue(root)
        except _UNAVAILABLE:
            gates = ()
        body = render_html(snapshot, evidence, project=project, gates=gates,
                           resources=self.server.measure_resources())
        return self._respond(200, body, "text/html; charset=utf-8")

    def do_GET(self) -> None:
        self._serve_read()

    def do_HEAD(self) -> None:
        self._serve_read()

    def do_POST(self) -> None:
        self._respond(405, b"read only", "text/plain; charset=utf-8")

    def do_OPTIONS(self) -> None:
        self._respond(405, b"read only", "text/plain; charset=utf-8")


class LocalStatusServer(ThreadingHTTPServer):
    allow_reuse_address = False
    daemon_threads = True

    def __init__(self, project_root: str | Path, port: int = 0):
        if type(port) is not int or not 0 <= port <= 65535:
            raise ValueError("invalid local port")
        self.project_root = Path(project_root).absolute()
        if self.project_root.drive.startswith(("\\\\", "//")):
            raise ValueError("dashboard checkout must be on a local drive")
        self.stylesheet = _CSS.read_bytes()
        self._sample_lock = Lock()
        _, self._previous_cpu = sample_local_resources()
        super().__init__(("127.0.0.1", port), DashboardHandler)

    def measure_resources(self) -> ResourceReading:
        with self._sample_lock:
            reading, self._previous_cpu = sample_local_resources(previous_cpu=self._previous_cpu)
        return reading


def launch_dashboard(project_root: str | Path, port: int = 0, *, open_browser: bool = False) -> None:
    """Serve the console until interrupted."""
    with LocalStatusServer(project_root, port=port) as server:
        url = f"http://127.0.0.1:{server.server_address[1]}/"
        print(f"MLA dashboard: {url}", flush=True)
        if open_browser:
            import webbrowser
            webbrowser.open(url, new=2)
        server.serve_forever(poll_interval=0.3)
