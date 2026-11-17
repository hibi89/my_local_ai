"""Explicit opt-in HTTP-only read-only loopback dashboard; P1 browser E2E deferred.

No POST/commands, no cookies, no JS, no CORS, no user data in public payloads.
Never starts on import; caller must explicitly run launch_dashboard() in P1.
"""
from __future__ import annotations

from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path

from .status_view import StatusSnapshot, load_snapshot

def host_allowed(host: str | None, port: int) -> bool:
    if not isinstance(host, str):
        return False
    return host in (f"127.0.0.1:{port}", f"localhost:{port}")

def origin_allowed(origin: str | None, port: int) -> bool:
    if origin is None:
        return True
    return origin in (f"http://127.0.0.1:{port}", f"http://localhost:{port}")

def render_html(snapshot: StatusSnapshot) -> bytes:
    state = snapshot.to_public_dict()
    percent = state["implementation_percent"]
    code_ready_names = ", ".join(escape(name) for name in state["p1_code_ready_ids"]) or "없음"
    text = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>My Local AI — Local Status</title>
<style>
:root{{color-scheme:dark;font-family:system-ui,-apple-system,sans-serif;background:#101827;color:#f6f8ff}}
body{{max-width:960px;margin:auto;padding:clamp(1rem,4vw,3rem);line-height:1.55}}
h1{{font-size:clamp(1.4rem,4vw,2rem)}}main{{display:grid;gap:1.25rem}}
.panel{{border:1px solid #43516b;border-radius:1rem;padding:1.3rem;background:#192338}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:.8rem}}
strong.value{{display:block;font-size:1.8rem}}
small,.muted{{color:#c1cde0}}
progress{{width:100%;height:1rem;accent-color:#8bb5ff}}
a{{color:#b5d4ff}}a:focus-visible{{outline:3px solid #fff;outline-offset:3px}}
</style></head><body>
<header><h1>My Local AI</h1><p class="muted">로컬 상태 보드 · 읽기 전용 · 자동 실행 비활성</p></header>
<main aria-label="작업 상태">
<section class="panel" aria-labelledby="impl"><h2 id="impl">구현 진행</h2>
<p><strong class="value">{percent:.2f}%</strong> {state['completed_req']} / {state['total_req']} REQ</p>
<progress max="100" value="{percent:.2f}" aria-label="구현완료율 {percent:.2f}퍼센트"></progress>
<p class="muted">구현 코드 후보와 실제 검증 통과는 다릅니다.</p></section>
<section class="cards" aria-label="작업 집계">
<div class="panel"><h2>코드 작성 READY (P1)</h2><strong class="value">{state['p1_code_ready_tasks']}</strong></div>
<div class="panel"><h2>실행 READY</h2><strong class="value">{state['ready_tasks']}</strong></div>
<div class="panel"><h2>HOLD/차단</h2><strong class="value">{state['hold_tasks']}</strong></div>
<div class="panel"><h2>코드 작성 후보</h2><strong class="value">{state['implemented_tasks']}</strong></div>
<div class="panel"><h2>전체 작업</h2><strong class="value">{state['task_total']}</strong></div></section>
<section class="panel" aria-labelledby="security"><h2 id="security">안전 게이트</h2>
<p>코드 작성 대기 작업: <strong>{code_ready_names}</strong> (실행 허가 아님)</p>
<p>단계: <strong>{escape(state['phase'])}</strong></p>
<p>실사용 승인: <strong>{"승인됨" if state["owner_real_use_go"] else "미승인"}</strong></p>
<p>중지·재개 제어: <strong>미연결 · 조회 전용</strong></p>
<p>P2 전체 검증: <strong>LOCKED</strong></p>
<p>공식 검증률: <strong>UNASSESSED</strong></p>
<p>Hydrogen 원격 워커: <strong>OFF (미승인)</strong></p>
<p>브라우저 전수 테스트: <strong>DEFERRED_TO_P2</strong></p>
<p>작업 시작·중지·승인 변경: <strong>이 읽기 전용 화면에서는 불가</strong></p></section>
</main><footer><small>로컬 전용. 고객 파일·비밀·모델 출력 미표시.</small></footer>
</body></html>"""
    return text.encode("utf-8")

class DashboardHandler(BaseHTTPRequestHandler):
    project_root: Path

    def log_message(self, format: str, *args) -> None:
        # No untrusted URL, query, Host, or raw headers are logged.
        return

    def _respond(self, status: int, payload: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def _serve_read(self) -> None:
        port = self.server.server_address[1]
        if (self.client_address[0] != "127.0.0.1"
            or not host_allowed(self.headers.get("Host"), port)
            or not origin_allowed(self.headers.get("Origin"), port)
            or self.headers.get("Sec-Fetch-Site", "none") not in ("none", "same-origin")):
            return self._respond(403, b"forbidden", "text/plain; charset=utf-8")
        if self.path not in ("/", "/status.json"):
            return self._respond(404, b"not found", "text/plain; charset=utf-8")
        try:
            snapshot = load_snapshot(self.server.project_root)
        except (ValueError, OSError, TypeError, KeyError):
            return self._respond(503, b"status unavailable", "text/plain; charset=utf-8")
        if self.path == "/status.json":
            body = json.dumps(snapshot.to_public_dict(), sort_keys=True).encode("ascii")
            return self._respond(200, body, "application/json; charset=utf-8")
        return self._respond(200, render_html(snapshot), "text/html; charset=utf-8")

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
        # Always bind IPv4 loopback only, never 0.0.0.0 or a LAN interface.
        super().__init__(("127.0.0.1", port), DashboardHandler)

def launch_dashboard(project_root: str | Path, port: int = 0) -> None:
    """Explicit blocking local-only server, never launched automatically."""
    with LocalStatusServer(project_root, port=port) as server:
        server.serve_forever(poll_interval=0.3)
