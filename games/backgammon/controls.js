// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0

/* Only input transport, edit history, and the font's terminal advance signal.
 * There is no SGF parser or board model in this file. */
const BACKGAMMON_EXAMPLES = {
  start: '(;GM[6])',
  opening: '(;FF[4]GM[6]CA[UTF-8];W[31hefe])',
  both: '(;GM[6];W[31hefe];B[31qtst])',
  hit: '(;GM[6];W[62xrmk];B[31qtst];W[61kehg];B[61agab])',
  entry: '(;GM[6];W[62xrmk];B[31qtst];W[61kehg];B[61agab];W[31yvxw])',
  roll: '(;GM[6];B[66])',
};

function backgammonText(source) {
  // Keep the whole program in one LTR shaping run, using only this font's cmap.
  // Unsupported Unicode/reserved transport characters become a rejection token;
  // they are never silently removed or interpreted by JavaScript.
  return '\ue000' + Array.from(source, char => {
    if ('\n\r\t'.includes(char)) char = ' ';
    const code = char >= ' ' && char <= '~' ? char.charCodeAt(0) : 127;
    return String.fromCharCode(0xe100 + code);
  }).join('') + '\ue001';
}

function backgammonSignal(width) {
  const signal = Math.round(width - 1800);
  return Math.abs(width - 1800 - signal) < 0.1 && signal >= 1 && signal <= 5 ? signal : 0;
}

function createBackgammonPlayground() {
  const get = id => document.querySelector('#' + id);
  const input = get('record'), drawing = get('drawing'), status = get('status');
  const probe = document.createElement('span');
  probe.className = 'probe';
  probe.setAttribute('aria-hidden', 'true');
  const holder = document.createElement('div');
  holder.className = 'probe-holder';
  holder.append(probe);
  document.body.append(holder);
  let loaded = false, previous = input.value, history = [], timer;
  const messages = [
    'The font did not produce a replay status. Check that ligatures are enabled.',
    'Replay complete. Explicit transfers applied; backgammon legality was not checked.',
    'Malformed input. The displayed board is a partial replay and should not be used.',
    'Unsupported SGF construct. See the supported subset below; the board is a partial replay.',
    'Replay limit reached: at most 128 turns. The board is a partial replay.',
    'Inconsistent transfer: empty or wrong-color source, blocked destination, or counter overflow. The board is a partial replay.',
  ];

  function measure(source) {
    probe.textContent = backgammonText(source);
    return backgammonSignal(probe.getBoundingClientRect().width);
  }
  function showStatus(message, signal = 0) {
    status.textContent = message;
    status.dataset.signal = String(signal);
    drawing.setAttribute('aria-label', message);
  }
  function clearResult(message) {
    drawing.textContent = '';
    probe.textContent = '';
    showStatus(message);
  }
  function render() {
    clearTimeout(timer);
    get('undo').disabled = !history.length;
    if (!loaded) return;
    if (input.value.length > 4096) {
      clearResult('Input limit reached: at most 4096 source characters in this playground.');
      return;
    }
    const signal = measure(input.value);
    if (!signal) {
      clearResult(messages[0]);
      return;
    }
    drawing.textContent = backgammonText(input.value);
    showStatus(messages[signal], signal);
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
    // The old board and its success signal describe different input now.
    if (loaded) clearResult('Replaying edited input…');
    timer = setTimeout(render, 100);
  });
  get('reset').onclick = () => replace(BACKGAMMON_EXAMPLES.start);
  get('load').onclick = () => replace(BACKGAMMON_EXAMPLES[get('example').value]);
  get('undo').onclick = () => {
    if (!history.length) return;
    input.value = previous = history.pop();
    render();
  };
  const ready = document.fonts.load('1000px BackgammonSGF', '\ue000W31\ue001').then(fonts => {
    if (!fonts.length || measure(BACKGAMMON_EXAMPLES.opening) !== 1 || measure('broken') !== 2) {
      throw new Error('Font or ligature support unavailable');
    }
    loaded = true;
    render();
  }).catch(() => {
    clearResult('Could not load or shape the backgammon font. Serve the repository over HTTP and enable standard ligatures.');
  });
  render();
  return {ready, render, replace};
}

if (typeof module !== 'undefined') {
  module.exports = {BACKGAMMON_EXAMPLES, backgammonText, backgammonSignal, createBackgammonPlayground};
}
