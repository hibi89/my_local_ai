'use strict';

(() => {
  const tracks = [
    { name: '픽셀 스타트', url: '/music-pixel-start.ogg' },
    { name: '버블 광장', url: '/music-bubble-square.ogg' },
    { name: '노을 언덕', url: '/music-sunset-hill.ogg' },
  ];
  const player = document.querySelector('#music');
  const title = document.querySelector('#music-title');
  const button = document.querySelector('#music-toggle');
  const label = document.querySelector('#music-toggle-label');
  let track = 0;
  let playing = false;
  let attempt = 0;
  player.volume = .25;

  function sync() {
    button.setAttribute('aria-pressed', String(playing));
    label.textContent = playing ? '음악 끄기' : '음악 켜기';
  }

  async function play() {
    const current = ++attempt;
    title.textContent = tracks[track].name;
    if (player.getAttribute('src') !== tracks[track].url) player.src = tracks[track].url;
    playing = true;
    sync();
    try {
      await player.play();
    } catch {
      if (current === attempt) {
        playing = false;
        title.textContent = '음악을 재생할 수 없습니다.';
        sync();
      }
    }
  }

  button.addEventListener('click', () => {
    if (!playing) {
      void play();
      return;
    }
    attempt++;
    player.pause();
    playing = false;
    sync();
  });
  document.querySelector('#music-next').addEventListener('click', () => {
    track = (track + 1) % tracks.length;
    title.textContent = tracks[track].name;
    if (playing) void play();
  });
})();
