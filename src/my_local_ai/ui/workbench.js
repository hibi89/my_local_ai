'use strict';

const session = document.body.dataset.session;
const form = document.querySelector('#draft-form');
const chatForm = document.querySelector('#chat-form');
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
const queueNotice = document.querySelector('#queue-notice');
const queueInspection = document.querySelector('#queue-inspection');
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
const itemLabels = { pending: '수정 지시 대기', working: '초안 작업 중', draft: '초안 저장됨', error: '작업 중단' };

let activeFile = null;
let renderedFolder = null;
let showDiff = true;
let retry = null;
let submission = 0;
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
  if (clock.state !== 'working') {
    displayForecast({ idle: '—', error: '중단', done: '완료', ready: '대기' }[clock.state] || '—');
  } else if (clock.saving) {
    displayForecast('저장 중');
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
    document.querySelector('#part-estimate').textContent = workQueue.active ? text : '대기';
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
    ['#inspection-notes', report.notes],
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
  itemOptions.hidden = !item || !workQueue.ready || queueWorking;
  showInspection(item?.inspection);
  if (!item) return;
  for (const button of queueItems.querySelectorAll('button')) {
    button.setAttribute('aria-pressed', String(button.dataset.item === id));
  }
  document.querySelector('#queue-selected-title').textContent = item.title;
  document.querySelector('#queue-detail').textContent = item.detail || item.title;
  const saved = document.querySelector('#queue-saved');
  saved.hidden = !item.draft;
  saved.textContent = item.draft ? item.draft.summary + '\n' + item.draft.folder : '';
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
  resumeQueue.hidden = !value.can_resume;
  const saved = items.filter(item => item.draft).length;
  const inspected = items.filter(item => item.inspection).length;
  document.querySelector('#queue-summary').textContent =
    items.length + '개 파트 · 읽기 검사 ' + inspected + '개 · 초안 ' + saved + '개 · 실행 검증 대기';
  nextItem.disabled = items.length < 2;
  const signature = JSON.stringify([value.id, value.active_mode, ...items.map(item =>
    [item.id, item.state, item.inspection?.state, item.auto_inspection])]);
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
      if (item.state === 'inspected') {
        status.textContent = item.inspection.state === 'observed' ? '읽기 확인 · 실행 대기' : '자료 확인 필요';
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
  const active = followActive && value.active;
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

nextItem.addEventListener('click', () => {
  if (!workQueue) return;
  const index = workQueue.items.findIndex(item => item.id === selectedItem);
  const following = [...workQueue.items.slice(index + 1), ...workQueue.items.slice(0, index)];
  const next = following.find(item => item.state === 'pending') || following[0];
  if (next) selectItem(next.id, true);
});

resumeQueue.addEventListener('click', async () => {
  if (!workQueue?.can_resume) return;
  const version = ++submission;
  clearTimeout(retry);
  resumeQueue.disabled = true;
  setBusy(true);
  try {
    const response = await fetch(session + '/start', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ queue: workQueue.id, resume: 'remaining' }),
    });
    const result = await response.json();
    if (!response.ok) {
      queueNotice.textContent = result.message;
      queueNotice.hidden = false;
      return;
    }
    showResult(result);
    if (result.state === 'working') retry = setTimeout(() => poll(version), 750);
  } catch {
    queueNotice.textContent = '자동 초안 재개 요청을 확인할 수 없습니다.';
    queueNotice.hidden = false;
  } finally {
    resumeQueue.disabled = false;
    if (!queueWorking) setBusy(false);
  }
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
  for (const input of forms) input.setAttribute('aria-busy', String(busy));
}

function showResult(state) {
  const stopped = state.state === 'error';
  const phaseMessage = stopped ? '' : state.message;
  if (phase.textContent !== phaseMessage) phase.textContent = phaseMessage;
  stateBadge.textContent = state.state === 'ready' && state.work_queue?.items.some(item => item.inspection)
    ? '읽기 검사 종료' : stateLabels[state.state];
  stateBadge.dataset.state = state.state;
  setBusy(state.state === 'working');
  attempt = state.attempt || '';
  showReplies(state.replies || []);
  showQueue(state.work_queue || null, state.state === 'working');
  replyForm.hidden = !state.can_reply;
  replyNotice.hidden = true;
  queueNotice.textContent = state.checkpoint_error || '';
  queueNotice.hidden = !state.checkpoint_error;
  if (typeof state.elapsed_ms === 'number') {
    clock = { running: state.state === 'working', at: performance.now(), elapsed: state.elapsed_ms,
      total: state.total_ms, state: state.state, forecast: state.forecast, saving: state.saving };
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

async function poll(version = submission) {
  try {
    const response = await fetch(session + '/status');
    if (!response.ok) throw new Error();
    const status = await response.json();
    if (version !== submission) return;
    showResult(status);
    if (status.state === 'working') retry = setTimeout(() => poll(version), 1100);
  } catch {
    if (version !== submission) return;
    showResult({ state: 'error', message: '작업대에 연결할 수 없습니다. 실행 창과 주소를 확인하세요.' });
  }
}

async function submit(event) {
  event.preventDefault();
  if (submitButtons[0].disabled) return;
  const version = ++submission;
  clearTimeout(retry);
  const input = event.currentTarget;
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
  setBusy(true);
  try {
    const response = await fetch(session + '/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const status = await response.json();
    if (!response.ok) {
      if (notice) {
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
    if (notice) {
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
