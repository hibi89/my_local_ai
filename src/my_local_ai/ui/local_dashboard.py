"""Explicit loopback server for the read-only MLA console."""
from __future__ import annotations

from contextlib import nullcontext
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
from threading import Lock
from urllib.parse import parse_qs, urlsplit

from ..ax_runtime.manual_draft import DraftError, LocalDrafts, REQUEST_LIMIT
from ..ax_runtime.workbench_guard import exclusive_workbench
from ..ops.resource_monitor import ResourceReading, sample_local_resources
from .dashboard_page import (
    load_locked_verification_queue, load_project_overview, render_html, render_unavailable,
)
from .status_view import load_snapshot, load_synthetic_evidence
from .workbench_page import render_workbench


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

    def _respond(self, status: int, payload: bytes, content_type: str, *, workbench=False) -> None:
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
                         "base-uri 'none'; form-action 'none';"
                         + (" script-src 'self'; connect-src 'self'; media-src 'self';" if workbench else ""))
        if status == 405:
            self.send_header("Allow", "GET, HEAD")
        self.end_headers()
        if self.command != "HEAD" and payload:
            self.wfile.write(payload)

    def _json(self, payload: dict, status=200) -> None:
        self._respond(status, json.dumps(payload, sort_keys=True).encode("ascii"),
                      "application/json; charset=utf-8")

    def _trusted_origin(self, *, require_origin=False) -> bool:
        port = self.server.server_address[1]
        hosts = self.headers.get_all("Host", [])
        origins = self.headers.get_all("Origin", [])
        fetch_sites = self.headers.get_all("Sec-Fetch-Site", ["none"])
        return (self.client_address[0] == "127.0.0.1" and len(hosts) == 1
                and host_allowed(hosts[0], port)
                and (origins == [f"http://{hosts[0]}"] or not origins and not require_origin)
                and fetch_sites in (["none"], ["same-origin"]))

    def _serve_read(self) -> None:
        if not self._trusted_origin():
            return self._respond(403, b"forbidden", "text/plain; charset=utf-8")
        if self.server.drafts is not None:
            if self.path in self.server.workbench_assets:
                asset, content_type = self.server.workbench_assets[self.path]
                return self._respond(200, asset, content_type)
            try:
                url = urlsplit(self.path)
            except ValueError:
                return self._respond(404, b"not found", "text/plain; charset=utf-8")
            if url.path == self.server.workbench_path and not url.netloc:
                layout = parse_qs(url.query).get("layout", ["desk"])[0]
                return self._respond(200, render_workbench(self.server.workbench_path, layout),
                                     "text/html; charset=utf-8", workbench=True)
            if self.path == self.server.workbench_path + "/status":
                return self._json(self.server.drafts.snapshot())
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
        if self.server.drafts is None or self.path != self.server.workbench_path + "/start":
            return self._respond(405, b"read only", "text/plain; charset=utf-8")
        if not self._trusted_origin(require_origin=True):
            return self._respond(403, b"forbidden", "text/plain; charset=utf-8")
        length = self.headers.get_all("Content-Length", [])
        content_types = self.headers.get_all("Content-Type", [])
        if (len(length) != 1 or re.fullmatch(r"[0-9]{1,8}", length[0]) is None
            or not 1 <= int(length[0]) <= REQUEST_LIMIT
            or content_types != ["application/json"] or self.headers.get_all("Transfer-Encoding")):
            return self._json({"message": "입력 형식 또는 문서 크기를 확인하세요."}, 400)
        try:
            data = self.rfile.read(int(length[0]))
            if len(data) != int(length[0]):
                raise ValueError("incomplete request")
            payload = json.loads(data)
            status = self.server.drafts.start(payload)
        except DraftError as exc:
            return self._json({"message": str(exc)}, 400)
        except (OSError, ValueError, RecursionError):
            return self._json({"message": "작업 요청을 읽을 수 없습니다."}, 400)
        return self._json(status, 202)

    def do_OPTIONS(self) -> None:
        self._respond(405, b"read only", "text/plain; charset=utf-8")


class LocalStatusServer(ThreadingHTTPServer):
    allow_reuse_address = False
    daemon_threads = True

    def __init__(self, project_root: str | Path, port: int = 0, *, drafts: LocalDrafts | None = None):
        if type(port) is not int or not 0 <= port <= 65535:
            raise ValueError("invalid local port")
        self.project_root = Path(project_root).absolute()
        if self.project_root.drive.startswith(("\\\\", "//")):
            raise ValueError("dashboard checkout must be on a local drive")
        self.stylesheet = _CSS.read_bytes()
        self.drafts = drafts
        self.workbench_path = "/work/" + secrets.token_urlsafe(32) if drafts is not None else ""
        self.workbench_assets = {}
        if drafts is not None:
            for name, kind in (
                ("workbench.css", "text/css; charset=utf-8"),
                ("workbench.js", "text/javascript; charset=utf-8"),
                ("workbench-music.js", "text/javascript; charset=utf-8"),
                ("music-pixel-start.ogg", "audio/ogg"),
                ("music-bubble-square.ogg", "audio/ogg"),
                ("music-sunset-hill.ogg", "audio/ogg"),
            ):
                self.workbench_assets["/" + name] = (
                    _CSS.with_name(name).read_bytes(), kind,
                )
        self._sample_lock = Lock()
        _, self._previous_cpu = sample_local_resources()
        super().__init__(("127.0.0.1", port), DashboardHandler)

    def measure_resources(self) -> ResourceReading:
        with self._sample_lock:
            reading, self._previous_cpu = sample_local_resources(previous_cpu=self._previous_cpu)
        return reading


def launch_dashboard(project_root: str | Path, port: int = 0, *, open_browser: bool = False,
                     draft_root: Path | None = None) -> None:
    """Serve the console until interrupted."""
    root = Path(draft_root).absolute() if draft_root is not None else None
    if root is not None:
        # Path validation and the OS lease precede queue restoration/auto-resume.
        from ..ax_runtime.worker_lock import _safe_directory
        _safe_directory(root.parent)
        root.mkdir(exist_ok=True)
    context = exclusive_workbench(root) if root is not None else nullcontext()
    with context:
        drafts = LocalDrafts(root) if root is not None else None
        with LocalStatusServer(project_root, port=port, drafts=drafts) as server:
            url = f"http://127.0.0.1:{server.server_address[1]}{server.workbench_path or '/'}"
            print(f"MLA dashboard: {url}", flush=True)
            if open_browser:
                import webbrowser
                webbrowser.open(url, new=2)
            server.serve_forever(poll_interval=0.3)
