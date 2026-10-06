// Shared movement bindings for both Snake playgrounds.
function bindSnakeControls(move) {
  const commands = {
    ArrowUp: 'w', ArrowLeft: 'a', ArrowDown: 's', ArrowRight: 'd',
    w: 'w', a: 'a', s: 's', d: 'd', W: 'w', A: 'a', S: 's', D: 'd',
    2: 'w', 4: 'a', 8: 's', 6: 'd',
  };
  document.querySelectorAll('[data-m]').forEach(button => {
    button.onclick = () => move(button.dataset.m);
  });
  addEventListener('keydown', event => {
    if (event.target.closest('input, textarea, select, [contenteditable]:not([contenteditable="false"])') ||
        event.ctrlKey || event.metaKey || event.altKey) return;
    const command = commands[event.key];
    if (!command) return;
    event.preventDefault();
    move(command);
  });
}

// The font reports a loss/win with one/two units of terminal-glyph advance.
// Measuring at 1000px (the fonts' UPM) reads that signal without duplicating
// their movement, food, growth, or collision rules in JavaScript.
function createSnakeSession({fontFamily, maxMoves, onRender, statusElement}) {
  const holder = document.createElement('div');
  holder.setAttribute('aria-hidden', 'true');
  holder.style.cssText = 'position:fixed;top:0;left:0;width:0;height:0;overflow:hidden;visibility:hidden;pointer-events:none';
  const probe = document.createElement('span');
  probe.style.cssText = `display:inline-block;width:max-content;white-space:pre;font:1000px/1 ${fontFamily};font-feature-settings:"liga" 1,"kern" 0;font-kerning:none;letter-spacing:normal;word-spacing:normal`;
  holder.append(probe);
  document.body.append(holder);
  const buttons = [...document.querySelectorAll('[data-m]')];
  const undoButton = document.querySelector('#undo');
  let prefix = '', boardAdvance = 0, moves = '', loaded = false, loadError = '';
  let state = 'loading';
  const messages = {
    loading: 'Loading game font…',
    playing: 'Playing.',
    lost: 'Game over. Undo or start a new game.',
    won: 'You won! Undo or start a new game.',
    limit: 'Move limit reached. Undo or start a new game.',
  };
  function signal(text) {
    probe.textContent = text;
    return Math.round(probe.getBoundingClientRect().width - boardAdvance);
  }
  function render() {
    onRender(prefix + moves, moves.length);
    if (loadError) state = 'error';
    else if (!loaded) state = 'loading';
    else {
      const terminal = signal(prefix + moves);
      state = terminal === 1 ? 'lost' : terminal === 2 ? 'won' :
        terminal === 0 ? (moves.length >= maxMoves ? 'limit' : 'playing') : 'error';
    }
    buttons.forEach(button => { button.disabled = state !== 'playing'; });
    undoButton.disabled = moves.length === 0;
    statusElement.textContent = loadError || messages[state] || 'The game font returned an invalid state. Rebuild the font.';
  }
  const ready = document.fonts.load(`1000px ${fontFamily}`, 'bwasd').then(fonts => {
    if (!fonts.length) throw new Error('Missing game font');
    if (signal(prefix + 'a') !== 1) {
      loadError = 'The game font is outdated or incompatible. Rebuild the font and reload.';
    } else loaded = true;
    render();
  }).catch(() => {
    loadError = 'The game font could not load. Serve the project root with python3 -m http.server 8000.';
    render();
  });
  return {
    ready,
    get state() { return state; },
    get moves() { return moves; },
    reset(nextPrefix, advance = 0) {
      prefix = nextPrefix; boardAdvance = advance; moves = ''; render();
    },
    move(command) {
      if (state !== 'playing' || !['w', 'a', 's', 'd'].includes(command)) return;
      moves += command; render();
    },
    undo() { moves = moves.slice(0, -1); render(); },
  };
}
