// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0

const PGM_MAX_SOURCE = 8192;
const PGM_EXAMPLES = {
  gradient: `P2
# Sixteen display-gray levels, from black to white
16 16
15
0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15
0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15
0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15
0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15
0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15
0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15
0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15
0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15
0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15
0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15
0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15
0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15
0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15
0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15
0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15
0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15`,
  checker: `P2
8 8
15
0 0 15 15 0 0 15 15
0 0 15 15 0 0 15 15
15 15 0 0 15 15 0 0
15 15 0 0 15 15 0 0
0 0 15 15 0 0 15 15
0 0 15 15 0 0 15 15
15 15 0 0 15 15 0 0
15 15 0 0 15 15 0 0`,
  shades: 'P2\n4 4\n15\n0 1 2 3\n4 5 6 7\n8 9 10 11\n12 13 14 15',
};

function pgmSource(value) {
  if (value.length > PGM_MAX_SOURCE) {
    throw new Error(`Use at most ${PGM_MAX_SOURCE} source characters.`);
  }
  // Lexical preparation only. Dimensions and pixels are read by the font.
  const source = value.replace(/#[^\r\n]*/g, '').replace(/[ \t\r\n\v\f]+/g, ' ').replace(/^ +| +$/g, '');
  if (/[^\x20-\x7e]/.test(source)) {
    throw new Error('Use ASCII text outside comments.');
  }
  return source;
}

function createPGMPlayground() {
  const program = document.querySelector('#program');
  const drawing = document.querySelector('#drawing');
  const raw = document.querySelector('#raw');
  const status = document.querySelector('#status');
  const holder = document.createElement('div');
  holder.className = 'probe-holder';
  holder.setAttribute('aria-hidden', 'true');
  const probe = document.createElement('span');
  probe.className = 'probe';
  holder.append(probe);
  document.body.append(holder);
  let loaded = false, loadError = '', state = 'loading';

  function width(source) {
    probe.textContent = source;
    return Math.round(probe.getBoundingClientRect().width);
  }

  function render() {
    let source = '', error = '';
    try {
      source = pgmSource(program.value);
    } catch (failure) {
      error = failure.message;
    }
    drawing.textContent = raw.textContent = source;
    if (error || loadError) {
      state = 'error';
      status.textContent = error || loadError;
    } else if (!loaded) {
      state = 'loading';
      status.textContent = 'Loading PGM font…';
    } else if (!source) {
      state = 'empty';
      status.textContent = 'Enter a P2 image or load an example.';
    } else {
      // An invalid run advances 2049 units. Valid image widths are multiples
      // of 64. This reads the font's result without interpreting the image.
      const advance = width(source);
      state = advance >= 64 && advance <= 2048 && advance % 64 === 0 ? 'ready' : 'error';
      status.textContent = state === 'ready' ? 'Image rendered by the font. Edit a sample to change a shade.' :
        'Invalid PGM. Use P2, dimensions 1–32, maxval 15, and exactly width × height samples (0–15).';
    }
    program.setAttribute('aria-invalid', String(state === 'error'));
  }

  program.addEventListener('input', render);
  document.querySelector('#load-example').onclick = () => {
    program.value = PGM_EXAMPLES[document.querySelector('#example').value];
    render();
  };
  document.querySelector('#clear').onclick = () => { program.value = ''; render(); };
  program.value = PGM_EXAMPLES.gradient;
  render();
  const ready = document.fonts.load('2048px PGMRenderer', 'P2 1 1 15 0').then(fonts => {
    if (!fonts.length || width('P2 1 1 15 0') !== 64 || width('P2 1 1 15 0 1') !== 2049) {
      throw new Error('Incompatible PGM font');
    }
    loaded = true;
    render();
  }).catch(() => {
    loadError = 'The PGM font could not load or shape. Serve the repository root and use the bundled font.';
    render();
  });
  return {ready, render, get state() { return state; }};
}

if (typeof module !== 'undefined') {
  module.exports = {pgmSource, PGM_EXAMPLES, PGM_MAX_SOURCE, createPGMPlayground};
}
