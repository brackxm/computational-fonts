// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0

const PPM_MAX_SOURCE = 8192;
const PPM_EXAMPLES = {
  bars: `P3
# RGB color bars
16 16
3
3 0 0 3 0 0 3 3 0 3 3 0 0 3 0 0 3 0 0 3 3 0 3 3 0 0 3 0 0 3 3 0 3 3 0 3 3 3 3 3 3 3 0 0 0 0 0 0
3 0 0 3 0 0 3 3 0 3 3 0 0 3 0 0 3 0 0 3 3 0 3 3 0 0 3 0 0 3 3 0 3 3 0 3 3 3 3 3 3 3 0 0 0 0 0 0
3 0 0 3 0 0 3 3 0 3 3 0 0 3 0 0 3 0 0 3 3 0 3 3 0 0 3 0 0 3 3 0 3 3 0 3 3 3 3 3 3 3 0 0 0 0 0 0
3 0 0 3 0 0 3 3 0 3 3 0 0 3 0 0 3 0 0 3 3 0 3 3 0 0 3 0 0 3 3 0 3 3 0 3 3 3 3 3 3 3 0 0 0 0 0 0
3 0 0 3 0 0 3 3 0 3 3 0 0 3 0 0 3 0 0 3 3 0 3 3 0 0 3 0 0 3 3 0 3 3 0 3 3 3 3 3 3 3 0 0 0 0 0 0
3 0 0 3 0 0 3 3 0 3 3 0 0 3 0 0 3 0 0 3 3 0 3 3 0 0 3 0 0 3 3 0 3 3 0 3 3 3 3 3 3 3 0 0 0 0 0 0
3 0 0 3 0 0 3 3 0 3 3 0 0 3 0 0 3 0 0 3 3 0 3 3 0 0 3 0 0 3 3 0 3 3 0 3 3 3 3 3 3 3 0 0 0 0 0 0
3 0 0 3 0 0 3 3 0 3 3 0 0 3 0 0 3 0 0 3 3 0 3 3 0 0 3 0 0 3 3 0 3 3 0 3 3 3 3 3 3 3 0 0 0 0 0 0
3 0 0 3 0 0 3 3 0 3 3 0 0 3 0 0 3 0 0 3 3 0 3 3 0 0 3 0 0 3 3 0 3 3 0 3 3 3 3 3 3 3 0 0 0 0 0 0
3 0 0 3 0 0 3 3 0 3 3 0 0 3 0 0 3 0 0 3 3 0 3 3 0 0 3 0 0 3 3 0 3 3 0 3 3 3 3 3 3 3 0 0 0 0 0 0
3 0 0 3 0 0 3 3 0 3 3 0 0 3 0 0 3 0 0 3 3 0 3 3 0 0 3 0 0 3 3 0 3 3 0 3 3 3 3 3 3 3 0 0 0 0 0 0
3 0 0 3 0 0 3 3 0 3 3 0 0 3 0 0 3 0 0 3 3 0 3 3 0 0 3 0 0 3 3 0 3 3 0 3 3 3 3 3 3 3 0 0 0 0 0 0
3 0 0 3 0 0 3 3 0 3 3 0 0 3 0 0 3 0 0 3 3 0 3 3 0 0 3 0 0 3 3 0 3 3 0 3 3 3 3 3 3 3 0 0 0 0 0 0
3 0 0 3 0 0 3 3 0 3 3 0 0 3 0 0 3 0 0 3 3 0 3 3 0 0 3 0 0 3 3 0 3 3 0 3 3 3 3 3 3 3 0 0 0 0 0 0
3 0 0 3 0 0 3 3 0 3 3 0 0 3 0 0 3 0 0 3 3 0 3 3 0 0 3 0 0 3 3 0 3 3 0 3 3 3 3 3 3 3 0 0 0 0 0 0
3 0 0 3 0 0 3 3 0 3 3 0 0 3 0 0 3 0 0 3 3 0 3 3 0 0 3 0 0 3 3 0 3 3 0 3 3 3 3 3 3 3 0 0 0 0 0 0`,
  palette: `P3
# All 64 RGB colors
8 8
3
0 0 0 0 0 1 0 0 2 0 0 3 0 1 0 0 1 1 0 1 2 0 1 3
0 2 0 0 2 1 0 2 2 0 2 3 0 3 0 0 3 1 0 3 2 0 3 3
1 0 0 1 0 1 1 0 2 1 0 3 1 1 0 1 1 1 1 1 2 1 1 3
1 2 0 1 2 1 1 2 2 1 2 3 1 3 0 1 3 1 1 3 2 1 3 3
2 0 0 2 0 1 2 0 2 2 0 3 2 1 0 2 1 1 2 1 2 2 1 3
2 2 0 2 2 1 2 2 2 2 2 3 2 3 0 2 3 1 2 3 2 2 3 3
3 0 0 3 0 1 3 0 2 3 0 3 3 1 0 3 1 1 3 1 2 3 1 3
3 2 0 3 2 1 3 2 2 3 2 3 3 3 0 3 3 1 3 3 2 3 3 3`,
  checker: 'P3\n2 2\n3\n3 0 0   0 3 0\n0 0 3   3 3 3',
};

function ppmSource(value) {
  if (value.length > PPM_MAX_SOURCE) {
    throw new Error(`Use at most ${PPM_MAX_SOURCE} source characters.`);
  }
  // Lexical preparation only. Dimensions and pixels are read by the font.
  const source = value.replace(/#[^\r\n]*/g, '').replace(/[ \t\r\n\v\f]+/g, ' ').replace(/^ +| +$/g, '');
  if (/[^\x20-\x7e]/.test(source)) {
    throw new Error('Use ASCII text outside comments.');
  }
  return source;
}

function createPPMPlayground() {
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
      source = ppmSource(program.value);
    } catch (failure) {
      error = failure.message;
    }
    drawing.textContent = raw.textContent = source;
    if (error || loadError) {
      state = 'error';
      status.textContent = error || loadError;
    } else if (!loaded) {
      state = 'loading';
      status.textContent = 'Loading PPM font…';
    } else if (!source) {
      state = 'empty';
      status.textContent = 'Enter a P3 image or load an example.';
    } else {
      // An invalid run advances 2049 units. Valid image widths are multiples
      // of 64. This reads the font's result without interpreting the image.
      const advance = width(source);
      state = advance >= 64 && advance <= 2048 && advance % 64 === 0 ? 'ready' : 'error';
      status.textContent = state === 'ready' ? 'Image rendered by the font. Edit RGB samples to change a color.' :
        'Invalid PPM. Use P3, dimensions 1–32, maxval 3, and three samples (0–3) per pixel.';
    }
    program.setAttribute('aria-invalid', String(state === 'error'));
  }

  program.addEventListener('input', render);
  document.querySelector('#load-example').onclick = () => {
    program.value = PPM_EXAMPLES[document.querySelector('#example').value];
    render();
  };
  document.querySelector('#clear').onclick = () => { program.value = ''; render(); };
  program.value = PPM_EXAMPLES.bars;
  render();
  const ready = document.fonts.load('2048px PPMRenderer', 'P3 1 1 3 0 0 0').then(fonts => {
    if (!fonts.length || width('P3 1 1 3 0 0 0') !== 64 || width('P3 1 1 3 0 0 0 1') !== 2049) {
      throw new Error('Incompatible PPM font');
    }
    loaded = true;
    render();
  }).catch(() => {
    loadError = 'The PPM font could not load or shape. Serve the repository root and use the bundled font.';
    render();
  });
  return {ready, render, get state() { return state; }};
}

if (typeof module !== 'undefined') {
  module.exports = {ppmSource, PPM_EXAMPLES, PPM_MAX_SOURCE, createPPMPlayground};
}
