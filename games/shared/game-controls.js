// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
// Text transport, edit history, and font status only. No board or strategy.
function gameText(source) {
  return '\ue000' + Array.from(source, char => {
    if ('\n\r\t'.includes(char)) char = ' ';
    const code = char >= ' ' && char <= '~' ? char.charCodeAt(0) : 127;
    return String.fromCharCode(0xe100 + code);
  }).join('') + '\ue001';
}

function gameSignal(width, frameWidth = 1800, count = 6) {
  const code = Math.round(width - frameWidth);
  return Math.abs(width - frameWidth - code) < .1 && code >= 1 && code <= count ? code : 0;
}

function createFontGame(config) {
  const get = id => document.querySelector('#' + id);
  const encode = config.encode || gameText;
  const input = get('record'), drawing = get('drawing'), status = get('status');
  const probe = document.createElement('span');
  probe.className = 'probe';
  probe.setAttribute('aria-hidden', 'true');
  const holder = document.createElement('div');
  holder.className = 'probe-holder';
  holder.append(probe);
  document.body.append(holder);
  const limit = config.limit || 1024, buttons = Array.from(document.querySelectorAll('[data-move]'));
  let loaded = false, previous = input.value, history = [], timer;
  function measure(source) {
    probe.textContent = encode(source);
    return gameSignal(probe.getBoundingClientRect().width, config.width || 1800, config.messages.length-1);
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
  function enableMoves(enabled) {
    for (const button of buttons) button.disabled = !enabled;
    if (get('play')) get('play').disabled = !enabled;
  }
  function render() {
    clearTimeout(timer);
    get('undo').disabled = !history.length;
    enableMoves(false);
    if (!loaded) return;
    if (input.value.length > limit) {
      clear(`Input limit reached: at most ${limit} source characters.`);
      return;
    }
    const code = measure(input.value);
    if (!code) { clear(config.messages[0]); return; }
    drawing.textContent = encode(input.value);
    show(config.messages[code], code);
    enableMoves(code === 1);
  }
  function replace(value) {
    if (value !== previous) history.push(previous);
    input.value = previous = value;
    render();
  }
  function propose(suffix) {
    if (!loaded) return;
    if (input.value.length > limit || measure(input.value) !== 1) { render(); return; }
    const candidate = input.value + suffix;
    if (candidate.length > limit) { show(`Move rejected: the history would exceed ${limit} characters.`); return; }
    const code = measure(candidate);
    if ((config.accepted || [1,2,3]).includes(code)) replace(candidate);
    else show(config.moveErrors?.[code] || 'Move rejected. '+config.messages[code], code);
  }
  input.addEventListener('input', () => {
    if (input.value !== previous) history.push(previous);
    previous = input.value;
    clearTimeout(timer);
    enableMoves(false);
    if (loaded) clear('Replaying edited history…');
    timer = setTimeout(render, 100);
  });
  get('reset').onclick = () => replace(config.newGame());
  get('undo').onclick = () => {
    if (!history.length) return;
    input.value = previous = history.pop();
    render();
  };
  for (const button of buttons) button.onclick = () => propose(button.dataset.move);
  if (get('play')) get('play').onclick = () => propose(config.move());
  const ready = document.fonts.load('1000px '+config.family, encode(config.tests[0][0])).then(fonts => {
    if (!fonts.length || config.tests.some(([source,code]) => measure(source) !== code)) {
      throw new Error('Font or ligature support unavailable');
    }
    loaded = true;
    render();
  }).catch(() => clear('Could not load or shape the font. Serve this repository over HTTP and enable standard ligatures.'));
  render();
  return {ready, render, replace, propose};
}

if (typeof module !== 'undefined') module.exports = {gameText, gameSignal, createFontGame};
