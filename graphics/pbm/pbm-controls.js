// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0

const PBM_MAX_SOURCE = 16384;

const PBM_HEART = [
  '0000000000000000',
  '0001110000111000',
  '0011111001111100',
  '0111111111111110',
  '0111111111111110',
  '0111111111111110',
  '0011111111111100',
  '0001111111111000',
  '0000111111110000',
  '0000011111100000',
  '0000001111000000',
  '0000000110000000',
  '0000000000000000',
  '0000000000000000',
  '0000000000000000',
  '0000000000000000',
];

function pbmExample(label, pixel) {
  // Generate built-in text examples only; user input is interpreted by the font.
  const rows = Array.from({length: 64}, (_, y) =>
    Array.from({length: 64}, (_, x) => pixel(x, y)).join(''));
  return ['P1', `# ${label}`, '64 64', ...rows].join('\n');
}

const PBM_EXAMPLES = {
  heart: pbmExample('A sixty-four-pixel heart', (x, y) => PBM_HEART[y >> 2][x >> 2]),
  checker: pbmExample('Eight-by-eight checkerboard', (x, y) => ((x >> 3) + (y >> 3)) % 2),
  diagonal: pbmExample('A one-pixel diagonal', (x, y) => Number(x === y)),
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
      // An invalid run advances 4097 units. Valid image widths are multiples
      // of 64. This reads the font's result without interpreting the image.
      const advance = width(source);
      state = advance >= 64 && advance <= 4096 && advance % 64 === 0 ? 'ready' : 'error';
      status.textContent = state === 'ready' ? 'Image rendered by the font. Edit a bit to change a pixel.' :
        'Invalid PBM. Use P1, dimensions 1–64, and exactly width × height bits (0 or 1).';
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
  const ready = document.fonts.load('4096px PBMRenderer', 'P1 1 1 0').then(fonts => {
    if (!fonts.length || width('P1 1 1 0') !== 64 || width('P1 1 1 01') !== 4097) {
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
