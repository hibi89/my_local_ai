"""The local draft workspace and its selectable layouts."""
from html import escape

LAYOUTS = {
    "desk": ("작업대", "입력과 결과를 한눈에"),
    "review": ("검토 중심", "변경 파일과 diff를 넓게"),
    "steps": ("순서형", "입력부터 검토까지 한 단계씩"),
}


def render_workbench(session_path: str, layout: str) -> bytes:
    if layout not in LAYOUTS:
        layout = "desk"
    selected = {layout: ' aria-current="page"'}
    tabs = "".join(
        f'<a class="layout-tab" href="?layout={key}"'
        f'{selected.get(key, "")}>'
        f'{label}<small>{description}</small></a>'
        for key, (label, description) in LAYOUTS.items()
    )
    return f"""<!doctype html>
<html lang="ko" data-layout="{layout}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MLA 작업대 · My Local AI</title>
  <link rel="stylesheet" href="/workbench.css">
  <script src="/workbench.js" defer></script>
  <script src="/workbench-music.js" defer></script>
</head>
<body data-session="{escape(session_path, quote=True)}">
  <a class="skip-link" href="#content">본문으로 이동</a>
  <header class="top">
    <div class="top-inner">
      <a class="brand-link" href="{escape(session_path, quote=True)}">
        <span class="brand-monogram" aria-hidden="true">M<span></span></span>
        <span>My Local AI</span>
      </a>
      <div class="top-meta">
        <div class="music-control" role="group" aria-label="배경음악">
          <span id="music-title" aria-live="polite">픽셀 스타트</span>
          <button type="button" id="music-toggle" class="quiet-button" aria-pressed="false">
            <span aria-hidden="true">♪</span> <span id="music-toggle-label">음악 켜기</span>
          </button>
          <button type="button" id="music-next" class="quiet-button">다음 곡</button>
          <audio id="music" loop preload="none"></audio>
        </div>
        <span class="model-name">Qwen3 4B</span><a href="/">시스템 상태</a>
      </div>
    </div>
  </header>
  <main id="content" class="shell">
    <header class="intro">
      <div><h1>로컬 작업대</h1><p>웹 GPT가 준 지시를 보내고, Qwen이 만든 변경 초안을 확인하세요.</p></div>
      <nav class="layout-tabs" aria-label="화면 구성">{tabs}</nav>
    </header>
    <ol class="steps" aria-label="작업 순서">
      <li>작업 자료 입력</li><li>로컬 Qwen 작업</li><li>변경 초안 검토</li>
    </ol>
    <div class="work-grid">
      <section class="panel inputs" aria-labelledby="input-heading">
        <header class="panel-head"><div><h2 id="input-heading">작업 지시</h2>
          <p>명령문과 GitHub 주소를 한 번에</p></div>
          <button type="button" class="quiet-button" id="sample">예제 넣기</button>
        </header>
        <form id="chat-form" aria-labelledby="input-heading">
          <label for="message">웹 GPT 지시문</label>
          <div class="composer">
            <textarea id="message" name="message" rows="8" required aria-describedby="chat-hint"
              placeholder="웹 GPT가 넘겨준 작업 지시를 그대로 붙여넣으세요.&#10;예시  GitHub의 최종설계도를 읽고 날짜 정렬 함수를 만들어줘."></textarea>
            <div class="composer-actions">
              <button class="primary" id="send" type="submit">보내고 작업 시작 <span aria-hidden="true">→</span></button>
              <kbd>Ctrl+Enter</kbd>
            </div>
          </div>
          <p id="chat-receipt" class="action-receipt" role="status" hidden></p>
          <p id="chat-hint">MLA가 작업 자료와 파일을 찾아 초안을 별도 폴더에 저장합니다.</p>
        </form>
        <details class="advanced-input">
          <summary>작업 자료 직접 지정</summary>
          <form id="draft-form">
          <label for="instructions">작업명령문</label>
          <textarea id="instructions" name="instructions" rows="5" required
            placeholder="예시  날짜 목록을 정렬하는 함수를 작성해줘"></textarea>
          <label for="blueprint">최종설계도 <small>같은 문서라면 생략 가능</small></label>
          <textarea id="blueprint" name="blueprint" rows="4"
            placeholder="설계 텍스트 또는 https://github.com/…"></textarea>
          <div class="file-inputs">
            <div>
              <label for="paths">작업 파일 <small>새 작업이면 생략 가능</small></label>
              <textarea id="paths" name="paths" rows="2" placeholder="src/date_tools.py"></textarea>
            </div>
            <div>
              <label for="workspace">기존 작업 폴더 <small>새 파일 작업이면 생략</small></label>
              <input id="workspace" name="workspace" type="text" placeholder="C:\\Projects\\my-app">
            </div>
          </div>
          <footer class="form-footer">
            <button class="primary" id="start" type="submit">로컬 작업 시작 <span aria-hidden="true">→</span></button>
            <span>초안은 별도 폴더에 저장됩니다.</span>
          </footer>
          </form>
        </details>
      </section>
      <section class="panel review" aria-labelledby="review-heading">
        <header class="panel-head"><div><h2 id="review-heading">작업 결과</h2>
          <p id="phase" role="status" aria-live="polite">작업을 시작하면 진행 상황이 표시됩니다.</p></div>
          <span id="state" class="state" data-state="idle">대기</span>
        </header>
        <dl class="timers" id="draft-timing" aria-label="작업 시간">
          <div><dt>이번 작업 시간</dt><dd><time id="elapsed" datetime="PT0S">00:00</time></dd></div>
          <div><dt>누적 작업 시간</dt><dd><time id="total" datetime="PT0S">00:00</time></dd></div>
          <div class="forecast">
            <dt>초안 예상 완료</dt>
            <dd><span id="forecast">—</span><small id="forecast-basis" hidden></small></dd>
          </div>
        </dl>
        <dl id="queue-timing" class="timers queue-timing" aria-label="전체와 현재 파트의 작업 시간" hidden>
          <div class="forecast"><dt>전체 예상 작업 시간</dt><dd><span id="queue-estimate">미산정</span><small id="queue-estimate-note"></small></dd></div>
          <div><dt>전체 경과 시간</dt><dd id="queue-elapsed">00:00</dd></div>
          <div class="forecast"><dt>현재 파트 예상 시간</dt><dd><span id="part-estimate">—</span><small id="part-estimate-note"></small></dd></div>
          <div><dt>현재 파트 경과 시간</dt><dd id="part-elapsed">—</dd></div>
        </dl>
        <p id="timing-warning" class="timing-warning" hidden>누적 시간을 저장할 수 없습니다.</p>
        <p id="queue-notice" class="timing-warning" role="status" hidden></p>
        <div class="result-body" id="result">
          <ol id="reply-history" class="reply-history" aria-label="내가 보낸 추가 지시" hidden></ol>
          <aside id="error-guide" class="error-guide" aria-label="MLA 안내" hidden>
            <span class="message-avatar" aria-hidden="true">M</span>
            <div class="error-message">
              <strong>MLA</strong>
              <p id="error-progress" hidden></p>
              <p id="error-message" role="status"></p>
              <p id="error-hint" hidden></p>
              <small id="error-code" hidden></small>
              <form id="reply-form" hidden>
                <label for="reply">MLA에 추가 지시</label>
                <textarea id="reply" name="reply" rows="2" maxlength="450" required
                  placeholder="예시  이 파일의 오류 메시지 한 곳만 고쳐줘"></textarea>
                <p id="reply-notice" role="status" hidden></p>
                <button type="submit" class="primary">답장하고 다시 시도 <span aria-hidden="true">→</span></button>
              </form>
              <button type="button" class="quiet-button" id="edit-message">입력창으로 이동</button>
            </div>
          </aside>
          <dl id="work-plan" class="work-plan" aria-label="자동으로 찾은 작업 범위" hidden></dl>
          <section id="work-queue" class="work-queue" aria-labelledby="queue-heading" hidden>
            <div class="queue-header">
              <div><h3 id="queue-heading">전체 작업</h3><p id="queue-summary"></p></div>
              <div class="queue-actions">
                <button type="button" id="resume-queue" class="quiet-button" hidden>자동 초안 재개</button>
                <button type="button" id="refresh-evidence" class="quiet-button" hidden>읽기 결과 다시 조회</button>
                <button type="button" id="next-item" class="quiet-button">다음 파트 보기</button>
              </div>
            </div>
            <p id="queue-receipt" class="action-receipt" role="status" hidden></p>
            <aside id="queue-hold" class="queue-hold" aria-label="작업 보류 사유" hidden>
              <strong id="queue-hold-title"></strong>
              <p id="queue-hold-reason"></p>
              <button type="button" id="view-blocker" class="quiet-button">이 파트 보기</button>
            </aside>
            <p id="advisor-state" class="advisor-state"></p>
            <ol id="queue-items" class="queue-items"></ol>
            <div id="queue-selection" class="queue-selection" hidden>
              <h4 id="queue-selected-title" tabindex="-1"></h4>
              <details class="sources">
                <summary>이 파트의 원래 지시</summary><p id="queue-detail"></p>
              </details>
              <section id="queue-inspection" class="queue-inspection" aria-label="이 파트의 읽기 검사" hidden>
                <h5>읽기 검사 결과</h5>
                <p id="inspection-sha"></p>
                <ul id="inspection-files"></ul>
                <ul id="inspection-notes"></ul>
                <p id="inspection-remaining"></p>
              </section>
              <p id="queue-saved" class="folder" hidden></p>
              <p id="item-recovery" class="item-recovery" hidden></p>
              <details id="item-options" class="sources" hidden>
                <summary>직접 수정 초안 요청</summary>
                <form id="item-form">
                  <label for="item-paths">수정 파일 경로</label>
                  <textarea id="item-paths" name="paths" rows="2" placeholder="프로젝트 상대 경로를 한 줄에 하나씩" required></textarea>
                  <label for="item-change">발견한 문제 또는 원하는 동작</label>
                  <textarea id="item-change" name="change" rows="3" maxlength="450" placeholder="재현한 오류나 바뀌어야 할 동작을 적어 주세요." required></textarea>
                  <p id="item-notice" role="status" hidden></p>
                  <button type="submit" class="primary">선택한 파트 초안 시작 <span aria-hidden="true">→</span></button>
                </form>
              </details>
            </div>
          </section>
          <div id="empty" class="empty">
            <div class="empty-icon" aria-hidden="true"><i></i><i></i><i></i></div>
            <strong>초안을 기다리는 중</strong>
            <p>파일 이름, 변경 내용, 저장 위치를 여기에서 확인합니다.</p>
          </div>
          <div id="details" hidden>
            <p id="summary" class="summary"></p>
            <div class="folder-row"><p id="folder" class="folder"></p>
              <button type="button" class="quiet-button" id="copy-folder">경로 복사</button></div>
            <nav id="file-list" class="file-list" aria-label="변경 파일"></nav>
            <div class="review-tools">
              <strong id="file-name"></strong>
              <div class="view-buttons">
                <button type="button" id="diff-view" aria-pressed="true">변경 비교</button>
                <button type="button" id="code-view" aria-pressed="false">전체 파일</button>
                <button type="button" id="copy-file">파일 내용 복사</button>
              </div>
            </div>
            <pre id="file-content" tabindex="0"></pre>
            <details class="sources"><summary>작업에 사용한 문서</summary><ul id="sources"></ul></details>
          </div>
        </div>
      </section>
    </div>
  </main>
</body>
</html>""".encode("utf-8")
