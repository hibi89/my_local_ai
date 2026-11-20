'use strict';

const session = document.body.dataset.session;
const form = document.querySelector('#draft-form');
const chatForm = document.querySelector('#chat-form');
const chatReceipt = document.querySelector('#chat-receipt');
const replyForm = document.querySelector('#reply-form');
const replyInput = replyForm.elements.reply;
const replyNotice = document.querySelector('#reply-notice');
const replyHistory = document.querySelector('#reply-history');
const itemForm = document.querySelector('#item-form');
const itemOptions = document.querySelector('#item-options');
const itemNotice = document.querySelector('#item-notice');
const queuePanel = document.querySelector('#work-queue');
const queueItems = document.querySelector('#queue-items');
const nextItem = document.querySelector('#next-item');
const resumeQueue = document.querySelector('#resume-queue');
const pauseContinuous = document.querySelector('#pause-continuous');
const resumeContinuous = document.querySelector('#resume-continuous');
const continuousState = document.querySelector('#continuous-state');
const refreshEvidence = document.querySelector('#refresh-evidence');
const queueNotice = document.querySelector('#queue-notice');
const queueReceipt = document.querySelector('#queue-receipt');
const holdBanner = document.querySelector('#queue-hold');
const blockerTitle = document.querySelector('#queue-hold-title');
const blockerReason = document.querySelector('#queue-hold-reason');
const viewBlocker = document.querySelector('#view-blocker');
const selectedTitle = document.querySelector('#queue-selected-title');
const advisorState = document.querySelector('#advisor-state');
const itemRecovery = document.querySelector('#item-recovery');
const queueInspection = document.querySelector('#queue-inspection');
const executeApproved = document.querySelector('#execute-approved');
const queueExecution = document.querySelector('#queue-execution');
const messageInput = chatForm.elements.message;
const forms = [chatForm, form, replyForm, itemForm];
const submitButtons = forms.map(current => current.querySelector('[type="submit"]'));
const phase = document.querySelector('#phase');
const stateBadge = document.querySelector('#state');
const fileList = document.querySelector('#file-list');
const fileContent = document.querySelector('#file-content');
const diffView = document.querySelector('#diff-view');
const codeView = document.querySelector('#code-view');
const copyFile = document.querySelector('#copy-file');
const copyFolder = document.querySelector('#copy-folder');
const details = document.querySelector('#details');
const empty = document.querySelector('#empty');
const errorGuide = document.querySelector('#error-guide');
const errorMessage = document.querySelector('#error-message');
const errorProgress = document.querySelector('#error-progress');
const errorHint = document.querySelector('#error-hint');
const errorCode = document.querySelector('#error-code');
const plan = document.querySelector('#work-plan');
const elapsed = document.querySelector('#elapsed');
const total = document.querySelector('#total');
const forecastText = document.querySelector('#forecast');
const forecastBasis = document.querySelector('#forecast-basis');
const stateLabels = { idle: '대기', working: '작업 중', ready: '작업표 준비됨', done: '초안 저장됨', error: '작업 중단' };
const itemLabels = { pending: '수정 지시 대기', working: '초안 작업 중', draft: '초안 저장됨',
  error: '작업 중단', inspected: '읽기 확인' };

let activeFile = null;
let renderedFolder = null;
let showDiff = true;
let retry = null;
let submission = 0;
let chatSubmission = null;
let queueSubmission = null;
let clock = null;
let renderedPlan = '';
let lastInput = chatForm;
let attempt = '';
let renderedReplies = '';
let workQueue = null;
let selectedItem = '';
let queueSignature = '';
let queueWorking = false;
let followActive = true;
let inspectedSignature = '';

document.querySelector('#sample').addEventListener('click', () => {
  if (!messageInput.value.trim()) {
    messageInput.value = '날짜 목록을 오름차순으로 정렬하는 Python 함수 sort_dates를 만들어줘.\n' +
      '작업 파일: src/date_tools.py\n입력과 반환값은 ISO 형식 날짜 목록이고, 원본 목록은 그대로 둬.';
  }
  messageInput.focus();
});
messageInput.addEventListener('keydown', event => {
  if (event.key === 'Enter' && (event.ctrlKey || event.metaKey) && !event.isComposing) {
    event.preventDefault();
    if (!submitButtons[0].disabled) chatForm.requestSubmit();
  }
});
document.querySelector('#edit-message').addEventListener('click', () => {
  if (lastInput === itemForm && !itemOptions.hidden) {
    itemOptions.open = true;
    itemForm.elements.change.focus();
  } else if (lastInput === form) {
    form.closest('details').open = true;
    form.elements.instructions.focus();
  } else {
    messageInput.focus();
  }
});

for (const tab of document.querySelectorAll('.layout-tab')) {
  tab.addEventListener('click', event => {
    if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    document.documentElement.dataset.layout = new URL(tab.href).searchParams.get('layout');
    history.replaceState(null, '', tab.href);
    document.querySelector('.layout-tab[aria-current]')?.removeAttribute('aria-current');
    tab.setAttribute('aria-current', 'page');
  });
}

function displayFile() {
  if (!activeFile) return;
  document.querySelector('#file-name').textContent =
    [activeFile.path, activeFile.syntax].filter(Boolean).join(' · ');
  diffView.setAttribute('aria-pressed', String(showDiff));
  codeView.setAttribute('aria-pressed', String(!showDiff));
  if (!showDiff) {
    fileContent.textContent = activeFile.content;
    return;
  }
  const rows = document.createDocumentFragment();
  for (const line of (activeFile.diff || '줄바꿈 형식이 변경되었습니다.').split('\n')) {
    const row = document.createElement('span');
    row.className = line.startsWith('+++') || line.startsWith('---') || line.startsWith('@@')
      ? 'diff-meta' : line.startsWith('+') ? 'diff-added' : line.startsWith('-') ? 'diff-removed' : '';
    row.textContent = line || ' ';
    rows.append(row);
  }
  fileContent.replaceChildren(rows);
}

diffView.addEventListener('click', () => { showDiff = true; displayFile(); });
codeView.addEventListener('click', () => { showDiff = false; displayFile(); });
copyFile.addEventListener('click', async () => {
  if (!activeFile) return;
  try {
    await navigator.clipboard.writeText(activeFile.content);
    copyFile.textContent = '복사됨';
    setTimeout(() => { copyFile.textContent = '파일 내용 복사'; }, 1400);
  } catch {
    phase.textContent = '복사 권한을 확인하거나 전체 파일에서 내용을 선택하세요.';
  }
});
copyFolder.addEventListener('click', async () => {
  if (!renderedFolder) return;
  try {
    await navigator.clipboard.writeText(renderedFolder);
    copyFolder.textContent = '복사됨';
    setTimeout(() => { copyFolder.textContent = '경로 복사'; }, 1400);
  } catch {
    phase.textContent = '저장 위치를 선택해 복사하세요.';
  }
});

function showTimeline() {
  if (!clock) return;
  const delta = clock.running ? performance.now() - clock.at : 0;
  if (workQueue) {
    document.querySelector('#queue-elapsed').textContent =
      timestamp(Math.floor((workQueue.elapsed_ms + delta) / 1000));
    const part = workQueue.items.find(item => item.id === workQueue.active);
    document.querySelector('#part-elapsed').textContent = part
      ? timestamp(Math.floor((part.elapsed_ms + delta) / 1000)) : '—';
  }
  for (const [node, ms] of [[elapsed, clock.elapsed], [total, clock.total]]) {
    const seconds = Math.floor((ms + delta) / 1000);
    const text = timestamp(seconds);
    if (node.textContent !== text) {
      node.textContent = text;
      node.dateTime = 'PT' + seconds + 'S';
    }
  }
  const estimate = clock.forecast;
  if (clock.disconnected) {
    displayForecast('연결 확인 필요');
  } else if (clock.state !== 'working') {
    displayForecast({ idle: '—', error: '중단', done: '완료', ready: '대기' }[clock.state] || '—');
  } else if (clock.saving) {
    displayForecast('저장 중');
  } else if (clock.recovering) {
    displayForecast('복구 중');
  } else if (!estimate) {
    displayForecast(workQueue?.active_mode === 'inspection' ? '읽기 검사 중' : '자료 확인 중');
  } else {
    const since = clock.elapsed + delta - estimate.from_elapsed_ms;
    const lower = Math.max(0, Math.ceil((estimate.lower_ms - since) / 1000));
    const upper = Math.max(0, Math.ceil((estimate.upper_ms - since) / 1000));
    const basis = estimate.runs ? '최근 성공 ' + estimate.runs + '회 기준' : '초기 추정';
    if (!upper) displayForecast('예상 범위 초과', 'Qwen 응답 대기 중');
    else if (!lower) displayForecast('약 ' + timestamp(upper) + ' 이내', basis);
    else displayForecast(timestamp(lower) + '–' + timestamp(upper) + ' 남음', basis);
  }
}

function timestamp(seconds) {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor(seconds / 60) % 60;
  const stamp = [minutes, seconds % 60].map(value => String(value).padStart(2, '0')).join(':');
  return hours ? hours + ':' + stamp : stamp;
}

function displayForecast(text, basis = '') {
  if (forecastText.textContent !== text) forecastText.textContent = text;
  if (forecastBasis.textContent !== basis) forecastBasis.textContent = basis;
  forecastBasis.hidden = !basis;
  if (workQueue) {
    document.querySelector('#part-estimate').textContent = workQueue.active ? text : workQueue.blocked ? '보류' : '대기';
    document.querySelector('#part-estimate-note').textContent = workQueue.active && basis ? '초안 · ' + basis : '';
  }
}

function showReplies(replies) {
  const key = JSON.stringify(replies);
  if (key === renderedReplies) return;
  renderedReplies = key;
  replyHistory.replaceChildren(...replies.map(reply => {
    const row = document.createElement('li');
    row.textContent = reply;
    return row;
  }));
  replyHistory.hidden = !replies.length;
}

function showInspection(report) {
  const signature = JSON.stringify(report || null);
  if (signature === inspectedSignature) return;
  inspectedSignature = signature;
  queueInspection.hidden = !report;
  if (!report) return;
  document.querySelector('#inspection-sha').textContent = '기준 커밋 ' + report.revision.slice(0, 12);
  for (const [target, rows] of [
    ['#inspection-files', report.files.map(file => file.path + ' · ' + file.result)],
    ['#inspection-notes', report.recheck_note ? [...report.notes, report.recheck_note] : report.notes],
  ]) {
    const list = document.querySelector(target);
    list.hidden = !rows.length;
    list.replaceChildren(...rows.map(text => {
      const row = document.createElement('li');
      row.textContent = text;
      return row;
    }));
  }
  document.querySelector('#inspection-remaining').textContent = '남은 검증 · ' + report.remaining;
}

function selectItem(id, selectedByUser = false) {
  if (selectedByUser) followActive = id === workQueue.active;
  if (selectedItem !== id) {
    itemForm.reset();
    itemNotice.hidden = true;
    itemOptions.open = false;
  }
  selectedItem = id;
  const item = workQueue?.items.find(row => row.id === id);
  document.querySelector('#queue-selection').hidden = !item;
  itemOptions.hidden = !item || !workQueue.ready || queueWorking || item.hold?.kind === 'dependency';
  showInspection(item?.inspection);
  executeApproved.hidden = !item?.can_execute;
  queueExecution.hidden = !item?.execution;
  if (item?.execution) {
    const execution = item.execution;
    document.querySelector('#execution-state').textContent =
      '상태 ' + execution.state + (execution.code ? ' · ' + execution.code : '') +
      ' · 고정 테스트 ' + execution.test_id;
    document.querySelector('#execution-evidence').textContent =
      '기준 SHA ' + execution.source_sha + ' · 실행 ID ' + (execution.run_id || '미확정') +
      ' · 결론 ' + (execution.conclusion || '미확정') + ' · 독립 검증 미실행';
    const url = document.querySelector('#execution-url');
    const expected = 'https://github.com/hibi89/REQ-Evidence-Auditor-A-/actions/runs/';
    const safe = Number.isSafeInteger(execution.run_id) && execution.run_id > 0 &&
      execution.url === expected + execution.run_id;
    url.hidden = !safe;
    url.removeAttribute('href');
    if (safe) url.href = execution.url;
  }
  if (!item) return;
  for (const button of queueItems.querySelectorAll('button')) {
    button.setAttribute('aria-pressed', String(button.dataset.item === id));
  }
  selectedTitle.textContent = item.title;
  document.querySelector('#queue-detail').textContent = item.detail || item.title;
  const saved = document.querySelector('#queue-saved');
  saved.hidden = !item.draft;
  saved.textContent = item.draft ? item.draft.summary + '\n' + item.draft.folder : '';
  const recovery = item.recovery;
  const note = recovery ? '실패 ' + recovery.failed_attempts + '/' + recovery.limit + '회' : '';
  const advisor = recovery?.advisor === 'gemini' ? 'Gemini 조언 반영' : recovery?.advisor === 'local' ? '로컬 재시도' : '';
  itemRecovery.textContent = [note, advisor, item.failure?.message, item.failure?.hint,
    item.hold?.kind === 'dependency' ? item.hold.detail : ''].filter(Boolean).join(' · ');
  itemRecovery.hidden = !itemRecovery.textContent;
}

function showQueue(value, working) {
  const changed = workQueue?.id !== value?.id;
  if (changed) followActive = true;
  workQueue = value;
  queueWorking = working;
  queuePanel.hidden = !value;
  document.querySelector('#draft-timing').hidden = Boolean(value);
  document.querySelector('#queue-timing').hidden = !value;
  if (!value) {
    selectedItem = queueSignature = '';
    return;
  }
  const items = value.items;
  resumeQueue.hidden = !value.can_resume || value.continuous?.paused;
  pauseContinuous.hidden = !value.can_pause;
  resumeContinuous.hidden = !value.can_continue;
  continuousState.textContent = value.continuous?.message || '장시간 진행 상태를 확인할 수 없습니다.';
  refreshEvidence.hidden = !value.can_refresh;
  const saved = items.filter(item => item.draft).length;
  const inspected = items.filter(item => item.inspection?.state === 'observed').length;
  const executed = items.filter(item => item.execution?.state === 'PASS').length;
  const held = items.filter(item => item.hold).length;
  const blocker = items.find(item => item.id === value.blocked);
  holdBanner.hidden = !blocker;
  if (blocker) {
    blockerTitle.textContent = blocker.title + ' · ' + blocker.hold.label;
    blockerReason.textContent = blocker.hold.detail;
  }
  advisorState.textContent = value.gemini_configured ? '복구 조언 · Gemini 키 설정됨' : '복구 조언 · 로컬 재시도';
  document.querySelector('#queue-summary').textContent =
    items.length + '개 파트 · 읽기 확인 ' + inspected + '개 · 초안 ' + saved + '개 · 실제 CLI 감사 완료 ' + executed + '개 · P2 수용 ' + value.verified_count + '개' +
    (held ? ' · 보류 ' + held + '개' : '');
  nextItem.disabled = items.length < 2;
  const signature = JSON.stringify([value.id, value.active_mode, ...items.map(item =>
    [item.id, item.state, item.inspection?.state, item.auto_inspection, item.hold?.kind, item.recovery?.failed_attempts, item.execution?.state, item.can_execute])]);
  if (queueSignature !== signature) {
    queueSignature = signature;
    queueItems.replaceChildren(...items.map(item => {
      const row = document.createElement('li');
      const button = document.createElement('button');
      const name = document.createElement('span');
      const status = document.createElement('small');
      button.type = 'button';
      button.dataset.item = item.id;
      button.addEventListener('click', () => selectItem(item.id, true));
      name.textContent = item.title;
      if (item.execution) {
        status.textContent = '실행 ' + item.execution.state;
      } else if (item.can_execute) {
        status.textContent = '실제 실행 승인 대기';
      } else if (item.hold) {
        status.textContent = item.state === 'inspected' && item.hold.kind === 'verification'
          ? '읽기 확인 · 검증 보류' : item.hold.label;
      } else if (item.state === 'working' && value.active_mode === 'inspection') {
        status.textContent = '읽기 검사 중';
      } else if (item.state === 'pending' && item.auto_inspection) {
        status.textContent = '읽기 검사 대기';
      } else {
        status.textContent = item.scheduled && item.state === 'pending' ? '자동 초안 대기' : itemLabels[item.state];
      }
      button.append(name, status);
      row.append(button);
      return row;
    }));
  }
  const active = followActive && (value.active || value.blocked);
  selectItem(active || (changed ? '' : selectedItem) || items[0]?.id);
  const windows = items.map(item => item.observation_hours).filter(Boolean);
  const sums = windows.reduce(([lo, hi], [left, right]) => [lo + left, hi + right], [0, 0]);
  const forecast = value.forecast;
  const draftEstimate = forecast
    ? [forecast.lower_ms, forecast.upper_ms].map(ms => timestamp(Math.ceil(ms * value.automated_count / 1000))).join('–')
    : '';
  document.querySelector('#queue-estimate').textContent = windows.length
    ? (sums[0] === sums[1] ? String(sums[0]) : sums.join('–')) + '시간 + 미산정'
    : draftEstimate ? draftEstimate + ' + 미산정' : '미산정';
  document.querySelector('#queue-estimate-note').textContent = windows.length
    ? '실측을 수행할 때의 관찰 시간' : draftEstimate ? '자동 초안 기준 · 실행 검증 미산정' : '구현·검증 범위 확인 필요';
}

executeApproved.addEventListener('click', () => {
  if (!workQueue || !selectedItem || executeApproved.hidden) return;
  runQueueAction({execute: 'reqea-manual', item: selectedItem});
});

nextItem.addEventListener('click', () => {
  if (!workQueue) return;
  const index = workQueue.items.findIndex(item => item.id === selectedItem);
  const following = [...workQueue.items.slice(index + 1), ...workQueue.items.slice(0, index)];
  const next = following.find(item => item.state === 'pending') || following[0];
  if (next) {
    selectItem(next.id, true);
    selectedTitle.focus();
  }
});

viewBlocker.addEventListener('click', () => {
  if (!workQueue?.blocked) return;
  selectItem(workQueue.blocked, true);
  selectedTitle.focus();
});

async function runQueueAction(command) {
  if (submitButtons[0].disabled && command.continuous !== 'pause') return;
  const version = ++submission;
  const previousAttempt = attempt;
  clearTimeout(retry);
  queueSubmission = { version, queue: workQueue.id, refresh: Boolean(command.refresh) };
  showReceipt(queueReceipt, command.execute ? '승인된 실제 GitHub 실행을 요청했습니다.' : command.refresh ? '읽기 결과를 다시 조회하는 중입니다.' : '초안 재개를 요청하는 중입니다.');
  setBusy(true);
  try {
    const response = await fetch(session + '/start', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ queue: workQueue.id, ...command }),
      signal: AbortSignal.timeout(12000),
    });
    const result = await response.json();
    if (!response.ok) {
      showReceipt(queueReceipt, result.message || '작업대가 요청을 받지 못했습니다.', 'error');
      setBusy(false);
      return;
    }
    showResult(result);
    if (result.state === 'working' || result.work_queue?.executing) retry = setTimeout(() => poll(version), 750);
  } catch {
    showReceipt(queueReceipt, '응답이 늦어 작업 상태를 확인 중입니다.');
    void poll(version, false, previousAttempt);
  }
}

resumeQueue.addEventListener('click', () => {
  if (workQueue?.can_resume) void runQueueAction({ resume: 'remaining' });
});
pauseContinuous.addEventListener('click', () => {
  if (workQueue?.can_pause) void runQueueAction({ continuous: 'pause' });
});
resumeContinuous.addEventListener('click', () => {
  if (workQueue?.can_continue) void runQueueAction({ continuous: 'resume' });
});
refreshEvidence.addEventListener('click', () => {
  if (workQueue?.can_refresh) void runQueueAction({ refresh: 'evidence' });
});

function showPlan(value) {
  const key = JSON.stringify(value || null);
  if (renderedPlan === key) return;
  renderedPlan = key;
  const ci = value?.baseline_ci;
  const reference = value?.reference_ci;
  const runs = evidence => evidence.runs.filter(run => run.conclusion === 'success').length +
    '/' + evidence.runs.length + '회 성공';
  const baseline = ci?.runs.length ? runs(ci) : ci ? '이 커밋의 실행 기록 없음' : value?.ci_unavailable ? '기록 조회 불가' : '';
  const entries = value ? [
    ['저장소', value.repository],
    ['브랜치', [value.branch, value.revision?.slice(0, 12)].filter(Boolean).join(' · ')],
    ['현재 파트', value.work_item],
    ['작업 파일', value.paths.join(', ')],
    ['기존 작업 폴더', value.workspace],
    ['작업 자료', value.documents ? `GitHub 문서 ${value.documents}개` : ''],
    ['기준 커밋 CI', baseline],
    ['이전 커밋 CI', reference?.runs.length ? reference.revision.slice(0, 12) + ' · ' + runs(reference) : ''],
  ].filter(([, data]) => data) : [];
  plan.hidden = !entries.length;
  plan.replaceChildren();
  for (const [label, data] of entries) {
    const field = document.createElement('div');
    const term = document.createElement('dt');
    const content = document.createElement('dd');
    term.textContent = label;
    content.textContent = data;
    field.append(term, content);
    plan.append(field);
  }
}

function setBusy(busy) {
  for (const button of submitButtons) button.disabled = busy;
  resumeQueue.disabled = busy;
  pauseContinuous.disabled = false; // Pausing is valid during a bounded in-flight step.
  resumeContinuous.disabled = busy;
  refreshEvidence.disabled = busy;
  executeApproved.disabled = busy;
  for (const input of forms) input.setAttribute('aria-busy', String(busy));
}

function showReceipt(node, text, tone = 'status') {
  if (node.textContent !== text) node.textContent = text;
  node.hidden = !text;
  node.dataset.tone = tone;
}

function showResult(state) {
  const stopped = state.state === 'error';
  const working = state.state === 'working';
  const blocker = state.work_queue?.items.find(item => item.id === state.work_queue.blocked);
  const holdMessage = blocker ? blocker.title + ' · ' + blocker.hold.detail : '';
  const phaseMessage = blocker ? '아래에서 다음 작업의 보류 사유를 확인할 수 있습니다.'
    : stopped ? '' : state.submission_notice || state.message;
  if (phase.textContent !== phaseMessage) phase.textContent = phaseMessage;
  if (chatSubmission === submission) {
    if (stopped && !state.submission_notice) {
      showReceipt(chatReceipt, state.message, 'error');
    } else if (blocker) {
      showReceipt(chatReceipt, '작업 보류 · ' + holdMessage, 'held');
    } else {
      showReceipt(chatReceipt, state.submission_notice || (state.state === 'done' ? '초안을 저장했습니다.' : '요청을 받았습니다.'));
    }
  }
  if (queueSubmission?.version === submission) {
    if (state.work_queue?.id !== queueSubmission.queue) {
      showReceipt(queueReceipt, '작업표가 바뀌었습니다. 현재 열린 작업표를 확인해 주세요.', 'held');
    } else if (working || stopped) {
      showReceipt(queueReceipt, state.message, stopped ? 'error' : 'status');
    } else if (queueSubmission.refresh) {
      showReceipt(queueReceipt, '읽기 결과 조회를 마쳤습니다. 실행 검증 ' + state.work_queue.verified_count + '개.');
    } else if (blocker) {
      showReceipt(queueReceipt, '작업 보류 · ' + holdMessage, 'held');
    } else {
      showReceipt(queueReceipt, state.message);
    }
  }
  stateBadge.textContent = blocker ? '작업 보류' : stateLabels[state.state];
  stateBadge.dataset.state = blocker ? 'held' : state.state;
  setBusy(working);
  attempt = state.attempt || '';
  showReplies(state.replies || []);
  showQueue(state.work_queue || null, working);
  replyForm.hidden = !state.can_reply;
  replyNotice.hidden = true;
  queueNotice.textContent = state.checkpoint_error || '';
  queueNotice.hidden = !state.checkpoint_error;
  if (typeof state.elapsed_ms === 'number') {
    clock = { running: state.state === 'working', at: performance.now(), elapsed: state.elapsed_ms,
      total: state.total_ms, state: state.state, forecast: state.forecast, saving: state.saving, recovering: state.recovering };
    document.querySelector('#timing-warning').hidden = state.timing_saved !== false;
    showTimeline();
  } else if (clock) {
    clock.running = false;
    clock.state = state.state;
    displayForecast('중단');
  }
  showPlan(state.plan);
  errorGuide.hidden = !stopped;
  errorMessage.textContent = stopped ? state.message : '';
  const documentsRead = state.plan && 'revision' in state.plan ? state.plan.documents : 0;
  errorProgress.hidden = !documentsRead;
  errorProgress.textContent = documentsRead ? 'GitHub 문서 ' + documentsRead + '개를 읽었어요.' : '';
  errorHint.hidden = !state.error?.hint;
  errorHint.textContent = state.error?.hint || '';
  errorCode.hidden = !state.error?.code;
  errorCode.textContent = state.error?.code ? '오류 코드 ' + state.error.code : '';
  details.hidden = state.state !== 'done';
  empty.hidden = !details.hidden || Boolean(workQueue) || stopped || (state.state === 'working' && !plan.hidden);
  if (state.state !== 'done' || renderedFolder === state.folder) return;
  renderedFolder = state.folder;
  document.querySelector('#summary').textContent = state.summary || '변경 파일을 확인하세요.';
  document.querySelector('#folder').textContent = state.folder;

  fileList.replaceChildren();
  for (const [index, file] of state.files.entries()) {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = file.path;
    button.setAttribute('aria-pressed', String(index === 0));
    button.addEventListener('click', () => {
      fileList.querySelector('[aria-pressed="true"]')?.setAttribute('aria-pressed', 'false');
      button.setAttribute('aria-pressed', 'true');
      activeFile = file;
      displayFile();
    });
    fileList.append(button);
  }
  activeFile = state.files[0];
  showDiff = true;
  displayFile();

  const sourceList = document.querySelector('#sources');
  sourceList.replaceChildren();
  for (const source of state.sources) {
    const item = document.createElement('li');
    const scope = source.characters_used === 0 && source.characters ? ' · 읽음, 모델에 전달할 문맥에서 제외' : source.characters_used < source.characters
      ? ' · 관련 발췌 ' + source.characters_used.toLocaleString('ko-KR') + '자/' + source.characters.toLocaleString('ko-KR') + '자'
      : ' · 전체 사용';
    item.textContent = [source.origin, source.revision].filter(Boolean).join(' · ') + scope;
    item.title = 'SHA-256 ' + source.sha256;
    sourceList.append(item);
  }
}

async function poll(version = submission, retried = false, confirmAttempt) {
  try {
    const response = await fetch(session + '/status', { signal: AbortSignal.timeout(12000) });
    if (!response.ok) throw new Error();
    const status = await response.json();
    if (version !== submission) return;
    showResult(status);
    if (confirmAttempt !== undefined && (status.attempt || '') === confirmAttempt && status.state !== 'working') {
      if (queueSubmission?.version === version) {
        showReceipt(queueReceipt, '조회 또는 재개 요청의 접수를 확인하지 못했습니다. 다시 눌러 주세요.', 'error');
      } else if (!status.submission_notice) {
        showReceipt(chatReceipt, '작업 접수가 확인되지 않았습니다. 다시 보내 주세요.', 'error');
      }
    }
    if (status.state === 'working' || status.work_queue?.executing) retry = setTimeout(() => poll(version), 1100);
  } catch {
    if (version !== submission) return;
    if (!retried) {
      phase.textContent = '작업 상태를 다시 확인 중입니다.';
      if (chatSubmission === version) showReceipt(chatReceipt, phase.textContent);
      if (queueSubmission?.version === version) showReceipt(queueReceipt, phase.textContent);
      retry = setTimeout(() => poll(version, true, confirmAttempt), 800);
      return;
    }
    phase.textContent = '작업대와 연결이 끊겼습니다. 실행기를 확인한 뒤 이 탭을 새로고침해 주세요.';
    if (chatSubmission === version) showReceipt(chatReceipt, phase.textContent, 'error');
    if (queueSubmission?.version === version) showReceipt(queueReceipt, phase.textContent, 'error');
    if (clock) {
      clock.running = false;
      clock.disconnected = true;
      showTimeline();
    }
    setBusy(false);
  }
}

async function submit(event) {
  event.preventDefault();
  if (submitButtons[0].disabled) return;
  const version = ++submission;
  clearTimeout(retry);
  const input = event.currentTarget;
  const chatting = input === chatForm;
  const previousAttempt = attempt;
  const replying = input === replyForm;
  const startingItem = input === itemForm;
  const notice = replying ? replyNotice : startingItem ? itemNotice : null;
  if (!replying) lastInput = input;
  const payload = Object.fromEntries(new FormData(input));
  if (replying) {
    payload.attempt = attempt;
    replyNotice.hidden = true;
  }
  if (startingItem) {
    if (!workQueue?.ready || !selectedItem) return;
    payload.queue = workQueue.id;
    payload.item = selectedItem;
    itemNotice.hidden = true;
  }
  chatSubmission = chatting ? version : null;
  showReceipt(queueReceipt, '');
  showReceipt(chatReceipt, chatting ? '시작 요청을 보내는 중입니다.' : '');
  setBusy(true);
  try {
    const response = await fetch(session + '/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(12000),
    });
    const status = await response.json();
    if (!response.ok) {
      if (chatting) {
        showReceipt(chatReceipt, status.message || '작업대가 요청을 받지 못했습니다.', 'error');
        setBusy(false);
      } else if (notice) {
        notice.textContent = status.message;
        notice.hidden = false;
        setBusy(false);
      } else {
        showResult({ state: 'error', message: status.message });
      }
      return;
    }
    if (replying) replyInput.value = '';
    showResult(status);
    if (status.state === 'working') retry = setTimeout(() => poll(version), 750);
  } catch {
    if (chatting) {
      showReceipt(chatReceipt, '접수 응답이 늦어 작업 상태를 확인 중입니다.');
      void poll(version, false, previousAttempt);
    } else if (notice) {
      notice.textContent = '요청을 전달하지 못했습니다. 이 탭에서 새로고침해 작업 상태를 확인하세요.';
      notice.hidden = false;
      setBusy(false);
    } else {
      showResult({ state: 'error', message: '작업 요청을 확인할 수 없습니다. 실행 창과 주소를 확인하세요.' });
    }
  }
}

for (const input of forms) input.addEventListener('submit', submit);
setInterval(showTimeline, 250);
poll();
