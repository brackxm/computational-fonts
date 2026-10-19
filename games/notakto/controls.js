// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
// Input transport and the font's advance signal only; no game model or strategy.
function notaktoText(source) {
  return '\ue000' + Array.from(source, char => {
    if ('\n\r\t'.includes(char)) char = ' ';
    const code = char >= ' ' && char <= '~' ? char.charCodeAt(0) : 127;
    return String.fromCharCode(0xe100 + code);
  }).join('') + '\ue001';
}

function notaktoSignal(width) {
  const code = Math.round(width - 1800);
  return Math.abs(width - 1800 - code) < .1 && code >= 1 && code <= 6 ? code : 0;
}

function createNotaktoPlayground() {
  const get = id => document.querySelector('#' + id);
  const input = get('record'), drawing = get('drawing'), status = get('status');
  const probe = document.createElement('span');
  probe.className = 'probe';
  probe.setAttribute('aria-hidden', 'true');
  const holder = document.createElement('div');
  holder.className = 'probe-holder';
  holder.append(probe);
  document.body.append(holder);
  const messages = [
    'The font did not return a status. Enable standard ligatures.',
    'Your turn. Choose an empty square on an open board.',
    'The font wins: you closed the last board. Undo to try another move.',
    'You win: the font closed the last board.',
    'Invalid move: that square is occupied or its board is closed. The display is a partial replay.',
    'Malformed history. Start with b, then pairs such as A2 or C9. The display is a partial replay.',
    'The font could not find a strategy move. Reset the game.',
  ];
  let loaded = false, previous = input.value, history = [], timer;
  function measure(source) {
    probe.textContent = notaktoText(source);
    return notaktoSignal(probe.getBoundingClientRect().width);
  }
  function show(message, code = 0) {
    status.textContent = message;
    status.dataset.signal = String(code);
    drawing.setAttribute('aria-label', message);
  }
  function clear(message) {
    drawing.textContent = probe.textContent = '';
    show(message);
  }
  function render() {
    clearTimeout(timer);
    get('undo').disabled = !history.length;
    if (!loaded) return;
    if (input.value.length > 256) {
      clear('Input limit reached: at most 256 source characters.');
      return;
    }
    const code = measure(input.value);
    if (!code) { clear(messages[0]); return; }
    drawing.textContent = notaktoText(input.value);
    show(messages[code], code);
  }
  function replace(value) {
    if (value !== previous) history.push(previous);
    input.value = previous = value;
    render();
  }
  input.addEventListener('input', () => {
    if (input.value !== previous) history.push(previous);
    previous = input.value;
    clearTimeout(timer);
    if (loaded) clear('Replaying edited history…');
    timer = setTimeout(render, 100);
  });
  get('reset').onclick = () => replace('b');
  get('undo').onclick = () => {
    if (!history.length) return;
    input.value = previous = history.pop();
    render();
  };
  for (const button of document.querySelectorAll('[data-move]')) {
    button.onclick = () => {
      if (!loaded || input.value.length > 254) return;
      if (measure(input.value) !== 1) { render(); return; }
      const candidate = input.value + button.dataset.move;
      const code = measure(candidate);
      if (code === 1 || code === 2 || code === 3) replace(candidate);
      else show(code === 4 ? 'Choose an empty square on an open board.' : messages[code], code);
    };
  }
  const ready = document.fonts.load('1000px NotaktoPerfect', '\ue000b\ue001').then(fonts => {
    if (!fonts.length || measure('b') !== 1 || measure('bA1') !== 4 || measure('bad') !== 5) {
      throw new Error('Font or ligature support unavailable');
    }
    loaded = true;
    render();
  }).catch(() => clear('Could not load or shape the font. Serve this repository over HTTP and enable standard ligatures.'));
  render();
  return {ready, render, replace};
}

if (typeof module !== 'undefined') module.exports = {notaktoText, notaktoSignal, createNotaktoPlayground};
