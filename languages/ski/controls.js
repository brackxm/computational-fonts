// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.SKI = api;
})(typeof globalThis === 'object' ? globalThis : this, function () {
  'use strict';
  const ALPHABET = 'SKIabcdefghijklmnopqrstuvwxyz';
  const DEPTH = 5, ROUNDS = 32;
  const EXAMPLES = {
    identity: {source: 'I a', fuel: 32},
    constant: {source: 'K a b', fuel: 32},
    substitution: {source: 'S K K a', fuel: 32},
    compound: {source: 'S (I a) b (I c)', fuel: 32},
    discard: {source: 'K a (S I I (S I I))', fuel: 32},
    budget: {source: 'S a b (K c d)', fuel: 1},
    partial: {source: 'S (I a)', fuel: 32},
    overflow: {source: 'S a b (a (a (a (a a))))', fuel: 32},
  };

  function parse(source) {
    if (typeof source !== 'string') throw new Error('Source must be text.');
    if (source.length > 16384) throw new Error('Use at most 16,384 source characters.');
    const text = source.replace(/\s/g, '');
    if (!text) throw new Error('Enter a SKI expression.');
    let index = 0;
    function prefix(depth = 0) {
      if (depth > 128) throw new Error('Expression nesting is too deep.');
      const char = text[index++];
      if (ALPHABET.includes(char) && char) return char;
      if (char === '@') return [prefix(depth + 1), prefix(depth + 1)];
      throw new Error('Invalid or incomplete prefix expression.');
    }
    function group(depth = 0) {
      if (depth > 128) throw new Error('Expression nesting is too deep.');
      let tree;
      while (index < text.length && text[index] !== ')') {
        const char = text[index++];
        let node;
        if (char === '(') {
          node = group(depth + 1);
          if (text[index++] !== ')') throw new Error('Close every parenthesis.');
        } else if (ALPHABET.includes(char)) node = char;
        else throw new Error('Use S, K, I, lowercase atoms and parentheses.');
        tree = tree === undefined ? node : [tree, node];
      }
      if (tree === undefined) throw new Error('Empty expression or parentheses.');
      return tree;
    }
    const tree = text.includes('@') ? prefix() : group();
    if (index !== text.length) throw new Error('Trailing expression or unmatched parenthesis.');
    return tree;
  }

  function inspect(source, fuel = ROUNDS) {
    if (!Number.isInteger(fuel) || fuel < 0 || fuel > ROUNDS) throw new Error('Fuel must be an integer from 0 to 32.');
    const tree = parse(source), todo = [[tree, 0]], output = [];
    let depth = 0;
    while (todo.length) {
      const [node, level] = todo.pop();
      depth = Math.max(depth, level);
      if (typeof node === 'string') output.push(node);
      else {
        output.push('@');
        todo.push([node[1], level + 1], [node[0], level + 1]);
      }
    }
    if (depth > DEPTH) throw new Error('Input exceeds the font’s depth of 5 edges (63 tree slots).');
    const prefix = output.join('');
    return {prefix, program: `SKI${fuel};${prefix}!` + '.'.repeat(191), depth, nodes: output.length, fuel};
  }

  function serialize(source, fuel = ROUNDS) { return inspect(source, fuel).program; }

  function createPlayground(document = globalThis.document) {
    const source = document.getElementById('source');
    const fuel = document.getElementById('fuel');
    const terminal = document.getElementById('terminal');
    const raw = document.getElementById('raw');
    const status = document.getElementById('status');
    const screen = document.getElementById('screen');
    const capacity = document.getElementById('capacity');
    let fontState = 'loading', fontError = '';
    function render() {
      try {
        if (!fuel.value.trim()) throw new Error('Enter a reduction budget from 0 to 32.');
        const data = inspect(source.value, Number(fuel.value));
        terminal.textContent = data.program;
        raw.textContent = data.program;
        capacity.textContent = `${data.nodes} of 63 tree slots · depth ${data.depth} of 5 · ${data.fuel} reduction${data.fuel === 1 ? '' : 's'} available`;
        screen.hidden = fontState !== 'ready';
        status.classList.toggle('error', fontState === 'error');
        status.textContent = fontState === 'ready' ? 'Ready. The font draws the result, status and remaining fuel.' :
          fontState === 'loading' ? 'Loading the SKI evaluator font…' : fontError + ' Serve the repository over HTTP and reload.';
      } catch (error) {
        terminal.textContent = ''; raw.textContent = ''; capacity.textContent = '';
        screen.hidden = true;
        status.classList.add('error'); status.textContent = error.message;
      }
    }
    source.addEventListener('input', render);
    fuel.addEventListener('input', render);
    for (const [id, example] of Object.entries(EXAMPLES)) {
      document.getElementById(id).addEventListener('click', () => {
        source.value = example.source; fuel.value = String(example.fuel); render();
      });
    }
    render();
    const ready = (async () => {
      try {
        const fonts = await document.fonts.load('24px SKIEvaluator', 'SKI;@Ia!');
        if (!fonts.length) throw new Error('The evaluator font could not load.');
        fontState = 'ready';
      } catch (error) { fontState = 'error'; fontError = error.message; }
      render();
    })();
    return {ready};
  }
  return {DEPTH, ROUNDS, EXAMPLES, parse, inspect, serialize, createPlayground};
});
