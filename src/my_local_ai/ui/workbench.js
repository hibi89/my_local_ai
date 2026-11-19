'use strict';

const session = document.body.dataset.session;
const form = document.querySelector('#draft-form');
const start = document.querySelector('#start');
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
const stateLabels = { idle: '대기', working: '작업 중', done: '초안 저장됨', error: '확인 필요' };

let activeFile = null;
let renderedFolder = null;
let showDiff = true;
let retry = null;

document.querySelector('#sample').addEventListener('click', () => {
  const examples = {
    instructions: '날짜 목록을 오름차순으로 정렬하는 Python 함수 sort_dates를 작성해줘.',
    blueprint: '함수의 입력과 반환값은 ISO 형식 날짜 목록이며, 원래 목록을 수정하지 않는다.',
    paths: 'src/date_tools.py',
  };
  for (const [key, value] of Object.entries(examples)) {
    if (!form.elements[key].value.trim()) form.elements[key].value = value;
  }
  form.elements.instructions.focus();
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

function showResult(state) {
  if (phase.textContent !== state.message) phase.textContent = state.message;
  stateBadge.textContent = stateLabels[state.state];
  stateBadge.dataset.state = state.state;
  start.disabled = state.state === 'working';
  form.setAttribute('aria-busy', String(start.disabled));
  details.hidden = state.state !== 'done';
  empty.hidden = !details.hidden || state.state === 'error';
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
    const scope = source.characters_used < source.characters
      ? ' · 관련 발췌 ' + source.characters_used.toLocaleString('ko-KR') + '자/' + source.characters.toLocaleString('ko-KR') + '자'
      : ' · 전체 사용';
    item.textContent = [source.origin, source.revision].filter(Boolean).join(' · ') + scope;
    item.title = 'SHA-256 ' + source.sha256;
    sourceList.append(item);
  }
}

async function poll() {
  try {
    const response = await fetch(session + '/status');
    if (!response.ok) throw new Error();
    const status = await response.json();
    showResult(status);
    if (status.state === 'working') retry = setTimeout(poll, 1100);
  } catch {
    showResult({ state: 'error', message: '작업대에 연결할 수 없습니다. 실행 창과 주소를 확인하세요.' });
  }
}

form.addEventListener('submit', async event => {
  event.preventDefault();
  clearTimeout(retry);
  if (start.disabled) return;
  start.disabled = true;
  try {
    const response = await fetch(session + '/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(Object.fromEntries(new FormData(form))),
    });
    const status = await response.json();
    if (!response.ok) {
      showResult({ state: 'error', message: status.message });
      return;
    }
    showResult(status);
    if (status.state === 'working') retry = setTimeout(poll, 750);
  } catch {
    showResult({ state: 'error', message: '작업 요청을 확인할 수 없습니다. 실행 창과 주소를 확인하세요.' });
  }
});

poll();
