// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.MiniBasic = api;
})(typeof globalThis === 'object' ? globalThis : this, function () {
  'use strict';
  const EXAMPLES = {
    count: '10 FOR A=1 TO 5\n20 PRINT A*A\n30 NEXT A\n40 END',
    step: '10 FOR A=1 TO 9 STEP 2\n20 PRINT A\n30 NEXT A\n40 END',
    greeting: '10 PRINT "Hello from a font!"\n20 A=7\n30 B=A*3\n40 PRINT B/2\n50 PRINT B MOD 2\n60 PRINT B-A\n70 END',
    branch: '10 LET D=9\n20 IF D<>0 THEN GOTO 40\n30 PRINT "This line is skipped"\n40 PRINT D\n50 LET D=D-1\n60 IF D>6 THEN GOTO 40\n70 END',
    subroutine: '10 A=3\n20 GOSUB 70\n30 PRINT A\n40 GOSUB 70\n50 PRINT A\n60 END\n70 A=A*2\n80 RETURN',
    logic: '10 A=3\n20 B=0\n30 IF A>0 AND NOT B=1 THEN 50\n40 END\n50 PRINT "MATCH"',
    while: '10 A=0\n20 WHILE A<3 AND NOT B=1\n30 PRINT A\n40 A=A+1\n50 WEND\n60 PRINT "DONE"',
    else: '10 FOR A=1 TO 4\n20 B=A MOD 2\n30 IF B=0 THEN 60 ELSE 40\n40 PRINT "ODD"\n50 GOTO 70\n60 PRINT "EVEN"\n70 NEXT A\n80 END',
    list: '10 A=7\n20 B=3\n30 PRINT "A=";A;", B=";B\n40 PRINT "sum=";A+B\n50 PRINT "difference=";A-B\n60 END',
    descending: '10 FOR A=9 TO 2 STEP -2\n20 PRINT "A=";A;", square=";A*A\n30 NEXT A\n40 END',
    limit: '10 REM This loop never ends\n20 GOTO 20',
  };
  function serialize(text) {
    const normalized = text.replace(/\r\n?/g, '\n');
    if (/[^\x20-\x7e\n]/.test(normalized)) throw new Error('Use printable ASCII characters.');
    const lines = normalized.split('\n').map(line => line.trim()).filter(Boolean);
    if (lines.length > 16) throw new Error('Use at most 16 program lines.');
    if (lines.some(line => line.length > 128)) throw new Error('Use at most 128 characters per program line.');
    return 'RUN:' + (lines.length ? lines.join(':') + ':' : '') + '!';
  }
  function createPlayground(document = globalThis.document) {
    const source = document.getElementById('source');
    const terminal = document.getElementById('terminal');
    const raw = document.getElementById('raw');
    const status = document.getElementById('status');
    const screen = document.getElementById('screen');
    let fontState = 'loading', fontError = '';
    function render() {
      try {
        const program = serialize(source.value);
        raw.textContent = program;
        terminal.textContent = program;
        screen.hidden = fontState !== 'ready';
        status.classList.toggle('error', fontState === 'error');
        status.textContent = fontState === 'ready' ? 'Ready. The font reruns the program whenever you edit it.' :
          fontState === 'loading' ? 'Loading the interpreter font…' : fontError + ' Serve the repository over HTTP and reload.';
      } catch (error) {
        terminal.textContent = '';
        raw.textContent = '';
        screen.hidden = true;
        status.classList.add('error');
        status.textContent = error.message;
      }
    }
    source.addEventListener('input', render);
    for (const [id, text] of Object.entries(EXAMPLES)) {
      document.getElementById(id).addEventListener('click', () => { source.value = text; render(); });
    }
    render();
    const ready = (async () => {
      try {
        const fonts = await document.fonts.load('2048px MiniBasic', 'RUN:!');
        if (!fonts.length) throw new Error('The interpreter font could not load.');
        fontState = 'ready';
      } catch (error) { fontState = 'error'; fontError = error.message; }
      render();
    })();
    return {ready};
  }
  return {EXAMPLES, serialize, createPlayground};
});
