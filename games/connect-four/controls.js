// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
// Input and presentation only. The font supplies the board and status advance.
function connectFourText(source) {
  return Array.from(source, c => {
    const cp = c.codePointAt(0);
    return String.fromCharCode(0xe100 + (cp >= 32 && cp <= 126 ? cp : 127));
  }).join('');
}
function connectFourSignal(width) {
  const code = Math.round(width - 1000);
  return Math.abs(width - 1000 - code) < 0.1 && code >= 1 && code <= 9 ? code : 0;
}
function createConnectFourPlayground() {
  const get = id => document.getElementById(id);
  const input = get('history'), drawing = get('drawing'), status = get('status');
  const buttons = Array.from(document.querySelectorAll('[data-column]'));
  const messages = [
    'Font computation unavailable. Serve this folder over HTTP and enable ligatures.',
    'Your turn. Choose a column for Yellow.',
    'Red wins. Reset to play again, or undo your last move.',
    'That column is full. The move was rejected; no computer reply was played. Undo to continue.',
    'Bad input. Start with b, then use only digits 1–7. Replay stopped at the first error.',
    'Red wins. Trailing input was ignored. Undo or edit the history to return to the game.',
    'Strategy error. The font could not complete this position.',
    'Yellow wins. This should be unreachable from a legal history under the pinned strategy.',
    'Draw. This should be unreachable from a legal history under the pinned strategy.',
    'Input limit reached. Undo or edit the history.',
  ];
  let loaded = false, signal = 0, timer = null;
  const probe = document.createElement('span');
  probe.className = 'probe'; probe.setAttribute('aria-hidden','true');
  document.body.append(probe);
  function setStatus(code, message = messages[code]) {
    signal = code;
    status.textContent = message; status.dataset.signal = String(code);
    drawing.setAttribute('aria-label',message);
    for (const b of buttons) b.disabled = !loaded || code !== 1;
    get('undo').disabled = input.value.length <= 1;
  }
  function clear(message) {
    drawing.textContent = ''; probe.textContent = ''; setStatus(0,message);
  }
  function measure(source) {
    probe.textContent = connectFourText(source);
    return connectFourSignal(probe.getBoundingClientRect().width);
  }
  function render() {
    clearTimeout(timer);
    if (!loaded) return;
    if (!input.value) { clear('Enter b to start a game.'); return; }
    if (input.value.length > 256) { clear('The playground accepts at most 256 characters.'); return; }
    const signal = measure(input.value);
    if (!signal) { clear(messages[0]); return; }
    drawing.textContent = connectFourText(input.value);
    setStatus(signal);
  }
  function replace(source) { input.value = source; render(); }
  function append(column) {
    if (loaded && signal === 1) replace(input.value+column);
  }
  input.addEventListener('input', () => {
    if (loaded) clear('Replaying edited history…');
    clearTimeout(timer); timer = setTimeout(render,80);
  });
  for (const b of buttons) b.onclick = () => append(b.dataset.column);
  get('undo').onclick = () => replace(Array.from(input.value).slice(0,-1).join('') || 'b');
  get('reset').onclick = () => replace('b');
  document.addEventListener('keydown', event => {
    if (event.target === input || event.ctrlKey || event.metaKey || event.altKey) return;
    if (/^[1-7]$/.test(event.key)) { event.preventDefault(); append(event.key); }
    if (event.key === 'Backspace') { event.preventDefault(); get('undo').onclick(); }
  });
  const resize = () => {
    drawing.style.fontSize = get('board-area').getBoundingClientRect().width + 'px';
  };
  if (typeof ResizeObserver !== 'undefined') new ResizeObserver(resize).observe(get('board-area'));
  resize(); setStatus(0,'Loading the game font…');
  const ready = Promise.resolve().then(() =>
    document.fonts.load('1000px ConnectFour', connectFourText('b1'))
  ).then(fonts => {
    if (!fonts.length || measure('b1') !== 1 || measure('b135') !== 2 || measure('b!') !== 4) {
      throw new Error('Shaping self-check failed');
    }
    loaded = true; render();
  }).catch(() => { loaded = false; clear(messages[0]); });
  return {ready,render,replace,measure};
}
if (typeof module !== 'undefined') module.exports = {connectFourText,connectFourSignal,createConnectFourPlayground};
