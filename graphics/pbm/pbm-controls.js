// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0

const PBM_MAX_SOURCE = 8192;
const PBM_EXAMPLES = {
  heart: `P1
# A thirty-two-pixel heart
32 32
00000000000000000000000000000000
00000000000000000000000000000000
00000011111100000000111111000000
00000011111100000000111111000000
00001111111111000011111111110000
00001111111111000011111111110000
00111111111111111111111111111100
00111111111111111111111111111100
00111111111111111111111111111100
00111111111111111111111111111100
00111111111111111111111111111100
00111111111111111111111111111100
00001111111111111111111111110000
00001111111111111111111111110000
00000011111111111111111111000000
00000011111111111111111111000000
00000000111111111111111100000000
00000000111111111111111100000000
00000000001111111111110000000000
00000000001111111111110000000000
00000000000011111111000000000000
00000000000011111111000000000000
00000000000000111100000000000000
00000000000000111100000000000000
00000000000000000000000000000000
00000000000000000000000000000000
00000000000000000000000000000000
00000000000000000000000000000000
00000000000000000000000000000000
00000000000000000000000000000000
00000000000000000000000000000000
00000000000000000000000000000000`,
  checker: `P1
8 8
00110011
00110011
11001100
11001100
00110011
00110011
11001100
11001100`,
  diagonal: 'P1\n4 4\n1000\n0100\n0010\n0001',
};

function pbmSource(value) {
  if (value.length > PBM_MAX_SOURCE) {
    throw new Error(`Use at most ${PBM_MAX_SOURCE} source characters.`);
  }
  // Lexical preparation only. Dimensions and pixels are read by the font.
  const source = value.replace(/#[^\r\n]*/g, '').replace(/[ \t\r\n\v\f]+/g, ' ').replace(/^ +| +$/g, '');
  if (/[^\x20-\x7e]/.test(source)) {
    throw new Error('Use ASCII text outside comments.');
  }
  return source;
}

function createPBMPlayground() {
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
      source = pbmSource(program.value);
    } catch (failure) {
      error = failure.message;
    }
    drawing.textContent = raw.textContent = source;
    if (error || loadError) {
      state = 'error';
      status.textContent = error || loadError;
    } else if (!loaded) {
      state = 'loading';
      status.textContent = 'Loading PBM font…';
    } else if (!source) {
      state = 'empty';
      status.textContent = 'Enter a P1 image or load an example.';
    } else {
      // An invalid run advances 2049 units. Valid image widths are multiples
      // of 64. This reads the font's result without interpreting the image.
      const advance = width(source);
      state = advance >= 64 && advance <= 2048 && advance % 64 === 0 ? 'ready' : 'error';
      status.textContent = state === 'ready' ? 'Image rendered by the font. Edit a bit to change a pixel.' :
        'Invalid PBM. Use P1, dimensions 1–32, and exactly width × height bits (0 or 1).';
    }
    program.setAttribute('aria-invalid', String(state === 'error'));
  }

  program.addEventListener('input', render);
  document.querySelector('#load-example').onclick = () => {
    program.value = PBM_EXAMPLES[document.querySelector('#example').value];
    render();
  };
  document.querySelector('#clear').onclick = () => { program.value = ''; render(); };
  program.value = PBM_EXAMPLES.heart;
  render();
  const ready = document.fonts.load('2048px PBMRenderer', 'P1 1 1 0').then(fonts => {
    if (!fonts.length || width('P1 1 1 0') !== 64 || width('P1 1 1 01') !== 2049) {
      throw new Error('Incompatible PBM font');
    }
    loaded = true;
    render();
  }).catch(() => {
    loadError = 'The PBM font could not load or shape. Serve the repository root and use the bundled font.';
    render();
  });
  return {ready, render, get state() { return state; }};
}

if (typeof module !== 'undefined') {
  module.exports = {pbmSource, PBM_EXAMPLES, PBM_MAX_SOURCE, createPBMPlayground};
}
