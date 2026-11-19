"""Render the Korean read-only console from allowlisted project status."""
from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path

from ..ops.resource_monitor import ResourceReading
from ..state.local_files import read_local_metadata
from ..state.source_progress import load_local_operator_swu_progress, load_v13_swu_progress
from .status_view import StatusSnapshot, SyntheticEvidenceSnapshot


_BLOCKERS = {
    "MLA-SWU-008": (
        "Windows 소유자 서명", "REQ-07",
        "별도 Windows 계정에서 승인 요청과 CNG 서명 왕복을 확인해야 합니다.",
    ),
    "MLA-SWU-021": (
        "F18 독립 실행 검증", "REQ-14 · REQ-15",
        "정적 검수 경로가 구현됐습니다. 독립 실행 테스트에는 승인된 격리 환경과 정확한 SHA의 결과가 필요합니다.",
    ),
    "CS-SWU-012": (
        "Defender 보호 스캔", "REQ-CS-08",
        "소유자가 승인한 합성 파일을 보호 서비스에서 스캔하고 대상 SHA와 결과를 대조해야 합니다.",
    ),
}

_VERIFICATION = {
    "MLA-V001": "빌드 · 패키징 · CI",
    "MLA-V002": "보안 · 권한 경계",
    "MLA-V003": "Windows · 로컬 모델",
    "MLA-V004": "독립 F18 · 소유자 서명",
    "MLA-V005": "SQLite · Git 복구",
    "MLA-V006": "24시간 무인 운용",
    "MLA-V007": "화면 · 브라우저",
    "MLA-V008": "요구사항별 증거 대조",
}


@dataclass(frozen=True)
class ProjectOverview:
    completed: int
    total: int
    breakdown: tuple[tuple[str, int, int], ...]
    pending_ids: tuple[str, ...]
    ready_count: int


def load_project_overview(root: Path) -> ProjectOverview:
    base = load_v13_swu_progress(root)
    overall = load_local_operator_swu_progress(root, base)
    queue = read_local_metadata(root / "P1_SWU_TASK_QUEUE.json")
    shield = read_local_metadata(root / "P1_V1_3_SWU_REBASELINE.json")
    operator = read_local_metadata(root / "docs" / "WINDOWS_LOCAL_OPERATOR_SWU_QUEUE.json")
    pending = {row["id"] for row in queue["tasks"]
               if row["code_status"] != "SOURCE_COMPLETE_P2_PENDING"}
    pending.update(row["id"] for row in shield["code_shield_swu_inventory"]
                   if not row["integrated_into_dev"])
    pending.update(row["id"] for row in operator["tasks"]
                   if row["code_status"] != "SOURCE_COMPLETE_P2_PENDING")
    completed = overall["overall_p1_source_swu_completed"]
    total = overall["overall_p1_source_swu_total"]
    if len(pending) != total - completed:
        raise ValueError("inconsistent source candidate queue")
    return ProjectOverview(
        completed, total,
        (
            ("MLA", base["legacy_mla_source_swu_completed"], base["legacy_mla_source_swu_total"]),
            ("CodeShield", base["codeshield_source_candidates_integrated_into_dev"],
             base["codeshield_feature_swu_total"]),
            ("Local Operator", overall["local_op_p1_swu_completed"], overall["local_op_p1_swu_total"]),
        ),
        tuple(key for key in _BLOCKERS if key in pending),
        len(queue["first_ready"]) + sum(row["code_status"] == "READY_CODE_ONLY"
                                        for row in operator["tasks"]),
    )


def load_locked_verification_queue(root: Path) -> tuple[str, ...]:
    ledger = read_local_metadata(root / "VERIFICATION_TASK_QUEUE.json")
    if (ledger.get("program") != "my_local_ai" or ledger.get("p2_verified_sha") is not None
        or ledger.get("verification_task_count") != len(_VERIFICATION)
        or not isinstance(ledger.get("tasks"), list)):
        raise ValueError("invalid verification ledger")
    records = [row for row in ledger["tasks"] if row["stage"] == "P2_VERIFICATION"]
    ids = tuple(row["task_id"] for row in records)
    if (len(ids) != len(_VERIFICATION) or set(ids) != set(_VERIFICATION)
        or any(row.get("verification_status") != "NOT_RUN" or row.get("evidence_sha") is not None
               or row.get("status") != "BLOCKED_BY_P1_GATE" for row in records)):
        raise ValueError("unverified gate state")
    return ids


def _shell(body: str) -> bytes:
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>운영 대시보드 · My Local AI</title>
  <link rel="stylesheet" href="/dashboard.css">
  <link rel="icon" href="/favicon.ico">
</head>
<body>{body}</body>
</html>""".encode("utf-8")


def render_unavailable() -> bytes:
    return _shell("""<main class="unavailable">
      <h1>운영 상태를 읽을 수 없습니다</h1>
      <p>MLA 작업 장부의 경로와 내용이 올바른지 확인한 뒤 다시 조회하세요.</p>
      <a class="button" href="/">다시 조회</a>
    </main>""")


def render_html(
    snapshot: StatusSnapshot,
    evidence: SyntheticEvidenceSnapshot | None = None,
    *,
    project: ProjectOverview | None = None,
    gates: tuple[str, ...] = (),
    resources: ResourceReading | None = None,
) -> bytes:
    state = snapshot.to_public_dict()
    if project is None:
        progress_value = '<span class="unmeasured">조회 불가</span>'
        progress_detail = '<p class="muted">소스 작업 장부를 확인하세요.</p>'
        queue_status = "소스 작업 장부 조회 불가"
        blocker_rows = ""
    else:
        progress_value = f'{project.completed}<span class="denominator">/{project.total}</span>'
        percent = 100 * project.completed / project.total
        breakdown = "".join(f"<li>{name} <b>{done}/{total}</b></li>"
                            for name, done, total in project.breakdown)
        progress_detail = f"""<progress value="{project.completed}" max="{project.total}"
              aria-label="P1 구현 후보 {percent:.2f}%"></progress>
            <ul class="breakdown">{breakdown}</ul>"""
        pending_count = project.total - project.completed
        queue_status = f"구현 대기 {pending_count}개 · 코드 작성 READY {project.ready_count}개"
        blocker_rows = ""
        for key in project.pending_ids:
            title, req, detail = _BLOCKERS[key]
            blocker_rows += f"""
              <details class="task">
                <summary><span class="task-main"><strong>{title}</strong>
                  <span class="task-id">{key}</span></span>
                  <span class="task-state">보호 검증 대기</span></summary>
                <p><code>{req}</code> · {detail}</p>
              </details>"""
        if pending_count > len(project.pending_ids):
            blocker_rows += '<p class="muted">추가 대기 작업은 소스 작업 장부에서 확인할 수 있습니다.</p>'
        if pending_count == 0:
            blocker_rows = '<p class="muted">구현 대기 작업이 없습니다.</p>'
    legacy_ready = ", ".join(escape(task_id) for task_id in state["p1_code_ready_ids"]) or "없음"

    if gates:
        gates_value = f'0<span class="denominator">/{len(gates)}</span>'
        gate_list = "".join(
            f'<li><span><strong>{_VERIFICATION[key]}</strong><code>{key}</code></span>'
            '<span class="muted">대기</span></li>' for key in gates
        )
        gate_rows = f'<ul class="gate-grid">{gate_list}</ul>'
    else:
        gates_value = '<span class="unmeasured">조회 불가</span>'
        gate_rows = '<p class="muted">검증 작업 장부를 읽을 수 없습니다.</p>'

    if evidence is None:
        evidence_card = '<p class="muted">기록된 합성 CI 보고를 읽을 수 없습니다.</p>'
    else:
        count = evidence.unit_tests + evidence.mock_integration_tests + evidence.security_tests
        evidence_card = f"""<div class="ci-record">
          <div><h3>합성 CI 보고</h3>
            <p class="muted">장부에 기록된 검사 {count}개 · 실행 번호 <code>{evidence.run_id}</code></p>
            <code class="sha">{escape(evidence.source_sha)}</code>
          </div>
          <a class="button" href="/evidence.json" download="mla-synthetic-ci.json">CI 기록 받기</a>
        </div>"""
    cpu = (f"{resources.cpu_percent:.0f}%" if resources and resources.cpu_percent is not None
           else "미측정")
    ram = (f"{resources.ram_mb / 1024:.1f} GiB" if resources and resources.ram_mb is not None
           else "미측정")

    return _shell(f"""
      <a class="skip" href="#main">본문으로 건너뛰기</a>
      <aside class="sidebar">
        <a class="brand" href="#overview"><span class="brand-mark" aria-hidden="true"><i></i><i></i><i></i></span>
          <span>My Local AI</span></a>
        <nav aria-label="주 메뉴">
          <a href="#overview"><span class="nav-icon nav-overview" aria-hidden="true"></span>운영 현황</a>
          <a href="#queue"><span class="nav-icon nav-queue" aria-hidden="true"></span>작업 대기열</a>
          <a href="#evidence"><span class="nav-icon nav-evidence" aria-hidden="true"></span>검증 근거</a>
          <a href="#system"><span class="nav-icon nav-system" aria-hidden="true"></span>시스템</a>
        </nav>
        <div class="sidebar-footer"><span class="local-dot" aria-hidden="true"></span>이 PC에서만 연결</div>
      </aside>
      <main id="main" class="workspace" tabindex="-1">
        <section id="overview" aria-labelledby="overview-title">
          <header class="page-heading">
            <div><p class="phase">P1 · 구현 단계</p><h1 id="overview-title">운영 대시보드</h1></div>
            <a class="button refresh" href="/"><span aria-hidden="true">↻</span> 새로고침</a>
          </header>
          <div class="release-banner">
            <div class="release-icon" aria-hidden="true">!</div>
            <div><h2>실행 보류</h2><p>Windows 보호 서명, 독립 실행 검증, 보호 스캔 증거가 필요합니다.</p></div>
            <a href="#queue">차단 항목 보기 <span aria-hidden="true">→</span></a>
          </div>
          <div class="metrics">
            <section class="panel metric" aria-labelledby="candidate-title">
              <h2 id="candidate-title">구현 후보 <span class="metric-unit">SWU</span></h2>
              <p class="metric-value">{progress_value}</p>{progress_detail}
            </section>
            <section class="panel metric" aria-labelledby="verification-title">
              <h2 id="verification-title">검증 게이트 <span class="badge">잠김</span></h2>
              <p class="metric-value">{gates_value}</p>
              <p class="muted">공식 검증률 미산정</p>
            </section>
            <section class="panel metric" aria-labelledby="runtime-title">
              <h2 id="runtime-title">실행 가능한 작업</h2>
              <p class="metric-value">{state['ready_tasks']}<span class="denominator">개</span></p>
              <p class="muted">실사용 승인 대기</p>
            </section>
          </div>
        </section>
        <div class="work-grid">
          <section id="queue" class="panel card" aria-labelledby="queue-title">
            <div class="section-heading"><h2 id="queue-title">작업 대기열</h2><p class="muted">{queue_status}</p></div>
            <div class="tasks">{blocker_rows}</div>
            <details class="legacy">
              <summary>기존 REQ 장부</summary>
              <p>기록된 REQ {state['completed_req']}/{state['total_req']}<br>
              코드 작성 READY (기존 큐) · <code>{legacy_ready}</code></p>
            </details>
          </section>
          <section id="system" class="panel card" aria-labelledby="system-title">
            <div class="section-heading"><h2 id="system-title">시스템</h2><p class="muted">읽기 전용</p></div>
            <dl class="system-list">
              <div><dt>현재 작업</dt><dd>대기 중</dd></div>
              <div><dt>기본 모델</dt><dd><code>qwen3:4b-instruct</code></dd></div>
              <div><dt>CPU</dt><dd>{cpu}</dd></div>
              <div><dt>사용 중인 RAM</dt><dd>{ram}</dd></div>
              <div><dt>VRAM · 온도</dt><dd>미측정</dd></div>
              <div><dt>시작 · 중지 · 재개</dt><dd>보호 환경 대기</dd></div>
            </dl>
            <details class="legacy">
              <summary>연결 정책</summary>
              <p>EAI 선택형 분석 · 기본 OFF<br>외부 모델 연결 · 사용 안 함</p>
            </details>
          </section>
        </div>
        <section id="evidence" class="panel card evidence" aria-labelledby="evidence-title">
          <div class="section-heading"><h2 id="evidence-title">검증 근거</h2>
            <a class="text-link" href="/status.json">기본 상태 JSON</a></div>
          {gate_rows}
          {evidence_card}
        </section>
      </main>""")
