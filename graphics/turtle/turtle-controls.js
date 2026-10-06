// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0

const TURTLE_MAX_COMMANDS = 128;
const TURTLE_EXAMPLES = {
  square: 'ffffl '.repeat(4).trim(),
  spiral: Array.from({length: 9}, (_, i) => 'f'.repeat(i + 1) + 'l').join(' '),
  stairs: 'fflffr '.repeat(4).trim(),
  gap: 'fff ufff dfff',
  colors: '1ffffl 2ffffl 3ffffl 5ffffl',
};

function turtleProgram(value) {
  const commands = value.toLowerCase().replace(/\s/g, '').replace(/^b/, '');
  if (!/^[flrud0-5]*$/.test(commands)) {
    throw new Error('Use F, L, R, U, D, and color commands 0–5, with an optional B at the start.');
  }
  if (commands.length > TURTLE_MAX_COMMANDS) {
    throw new Error(`Use at most ${TURTLE_MAX_COMMANDS} commands; remove commands to continue.`);
  }
  return commands;
}

function createTurtlePlayground() {
  const program = document.querySelector('#program');
  const drawing = document.querySelector('#drawing');
  const raw = document.querySelector('#raw');
  const status = document.querySelector('#status');
  const count = document.querySelector('#count');
  const undo = document.querySelector('#undo');
  const buttons = [...document.querySelectorAll('[data-command]')];
  const holder = document.createElement('div');
  holder.className = 'probe-holder';
  holder.setAttribute('aria-hidden', 'true');
  const probe = document.createElement('span');
  probe.className = 'probe';
  holder.append(probe);
  document.body.append(holder);
  let loaded = false, loadError = '', commands = '', state = 'loading';

  function width(text) {
    probe.textContent = text;
    return Math.round(probe.getBoundingClientRect().width);
  }

  function render() {
    let error = '';
    try {
      commands = turtleProgram(program.value);
      drawing.textContent = raw.textContent = 'b' + commands;
      program.setAttribute('aria-invalid', 'false');
      count.textContent = `${commands.length} / ${TURTLE_MAX_COMMANDS}`;
    } catch (failure) {
      error = failure.message;
      program.setAttribute('aria-invalid', 'true');
      count.textContent = '';
    }
    if (loadError || error) {
      state = 'error';
      status.textContent = loadError || error;
    } else if (!loaded) {
      state = 'loading';
      status.textContent = 'Loading turtle font…';
    } else {
      // The board advances 2100 units; the terminal X adds one. The font
      // handles position, heading, pen state, and line generation itself.
      const signal = width('b' + commands) - 2100;
      state = signal === 1 ? 'blocked' : signal !== 0 ? 'error' :
        commands.length === TURTLE_MAX_COMMANDS ? 'limit' : 'ready';
      status.textContent = {
        ready: 'Ready. Append a command to draw.',
        blocked: 'Canvas boundary reached. Undo or edit the commands to continue.',
        limit: 'Command limit reached. Undo or edit the commands to continue.',
        error: 'The font returned an invalid drawing. Rebuild the font and reload.',
      }[state];
    }
    buttons.forEach(button => { button.disabled = state !== 'ready'; });
    undo.disabled = !!error || commands.length === 0;
  }

  function move(command) {
    if (state !== 'ready' || !/^[flrud0-5]$/.test(command)) return;
    program.value = commands + command;
    render();
  }
  program.addEventListener('input', render);
  buttons.forEach(button => { button.onclick = () => move(button.dataset.command); });
  undo.onclick = () => {
    program.value = commands.slice(0, -1);
    render();
  };
  document.querySelector('#reset').onclick = () => { program.value = ''; render(); };
  document.querySelector('#load-example').onclick = () => {
    program.value = TURTLE_EXAMPLES[document.querySelector('#example').value];
    render();
  };
  addEventListener('keydown', event => {
    if (event.target.closest('input, textarea, select, [contenteditable]:not([contenteditable="false"])') ||
        event.ctrlKey || event.metaKey || event.altKey) return;
    const command = ({ArrowUp: 'f', ArrowLeft: 'l', ArrowRight: 'r'})[event.key] || event.key.toLowerCase();
    if (!/^[flrud0-5]$/.test(command)) return;
    event.preventDefault();
    move(command);
  });
  render();
  const ready = document.fonts.load('1000px TurtleGraphics', 'bflrud012345').then(fonts => {
    if (!fonts.length) throw new Error('Missing turtle font');
    if (width('b') !== 2100 || width('b1' + 'f'.repeat(11)) !== 2101) {
      loadError = 'The turtle font is incompatible. Use the bundled 21×21 font with ligatures enabled.';
    } else {
      loaded = true;
    }
    render();
  }).catch(() => {
    loadError = 'The turtle font could not load. Serve the project root with python3 -m http.server 8000.';
    render();
  });
  return {ready, move, get state() { return state; }};
}

if (typeof module !== 'undefined') {
  module.exports = {turtleProgram, TURTLE_EXAMPLES, TURTLE_MAX_COMMANDS, createTurtlePlayground};
}
