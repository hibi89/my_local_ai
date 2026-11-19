'use strict';

const session = document.body.dataset.session;
const form = document.querySelector('#draft-form');
const chatForm = document.querySelector('#chat-form');
const messageInput = chatForm.elements.message;
const forms = [chatForm, form];
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
const stateLabels = { idle: '대기', working: '작업 중', done: '초안 저장됨', error: '작업 중단' };

let activeFile = null;
let renderedFolder = null;
let showDiff = true;
let retry = null;
let submission = 0;
let clock = null;
let renderedPlan = '';
let lastInput = chatForm;

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
  if (lastInput === form) {
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
  for (const [node, ms] of [[elapsed, clock.elapsed], [total, clock.total]]) {
    const seconds = Math.floor((ms + delta) / 1000);
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor(seconds / 60) % 60;
    const stamp = [minutes, seconds % 60].map(value => String(value).padStart(2, '0')).join(':');
    const text = hours ? hours + ':' + stamp : stamp;
    if (node.textContent !== text) {
      node.textContent = text;
      node.dateTime = 'PT' + seconds + 'S';
    }
  }
}

function showPlan(value) {
  const key = JSON.stringify(value || null);
  if (renderedPlan === key) return;
  renderedPlan = key;
  const entries = value ? [
    ['저장소', value.repository],
    ['브랜치', [value.branch, value.revision?.slice(0, 12)].filter(Boolean).join(' · ')],
    ['작업 파일', value.paths.join(', ')],
    ['기존 작업 폴더', value.workspace],
    ['작업 자료', value.documents ? `GitHub 문서 ${value.documents}개` : ''],
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
  stateBadge.textContent = stateLabels[state.state];
  stateBadge.dataset.state = state.state;
  setBusy(state.state === 'working');
  if (typeof state.elapsed_ms === 'number') {
    clock = { running: state.state === 'working', at: performance.now(), elapsed: state.elapsed_ms, total: state.total_ms };
    document.querySelector('#timing-warning').hidden = state.timing_saved !== false;
    showTimeline();
  } else if (clock) {
    clock.running = false;
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
  empty.hidden = !details.hidden || state.state === 'error' || (state.state === 'working' && !plan.hidden);
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
  lastInput = event.currentTarget;
  const payload = Object.fromEntries(new FormData(event.currentTarget));
  setBusy(true);
  try {
    const response = await fetch(session + '/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const status = await response.json();
    if (!response.ok) {
      showResult({ state: 'error', message: status.message });
      return;
    }
    showResult(status);
    if (status.state === 'working') retry = setTimeout(() => poll(version), 750);
  } catch {
    showResult({ state: 'error', message: '작업 요청을 확인할 수 없습니다. 실행 창과 주소를 확인하세요.' });
  }
}

for (const input of forms) input.addEventListener('submit', submit);
setInterval(showTimeline, 250);
poll();
