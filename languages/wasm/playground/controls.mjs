// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
import {parseInteger, registerLayout} from './runtime.mjs';

export function errorMessage(error) {
  if (error.name === 'WasmTrap') return `Wasm trap: ${error.message.replaceAll('_', ' ')}. No result is valid.`;
  if (error.name === 'ExecutionBoundExceeded') return `Execution bound exceeded: ${error.message}. Try a smaller input or rebuild with larger bounds. No result is valid.`;
  return error.message || 'The font could not run.';
}

export function createPlayground(doc = document) {
  const element = id => doc.getElementById(id);
  const select = element('example'), run = element('run'), status = element('status');
  const parameters = element('parameters'), results = element('results');
  const assets = new URL('./assets/', import.meta.url);
  let worker, manifest, inputs = [], catalog = [], generation = 0, request = 0, timer;
  let loaded = false;
  let customProgram;
  let resultLabels = [];

  function state(name, message) {
    status.dataset.state = name;
    status.textContent = message;
    run.disabled = !loaded || name === 'running';
    if (name !== 'ready') results.replaceChildren();
  }

  function showResult(reply) {
    results.replaceChildren();
    reply.results.forEach((result, index) => {
      const card = doc.createElement('section');
      card.className = 'result';
      const heading = doc.createElement('h2');
      heading.textContent = `${resultLabels[index] || 'Result ' + (index + 1)} · ${result.type} · unsigned`;
      const number = doc.createElement('div');
      number.className = 'number';
      number.textContent = result.unsigned;
      const values = doc.createElement('dl');
      for (const [label, text] of [['Signed', result.signed], ['Hex', result.hex],
          ['Bits', result.binary.match(/.{1,8}/g).join(' ')]]) {
        const term = doc.createElement('dt'), value = doc.createElement('dd');
        term.textContent = label; value.textContent = text;
        values.append(term, value);
      }
      card.append(heading, number, values);
      results.append(card);
    });
    if (!reply.results.length) results.textContent = 'Completed with no return values.';
    state('ready', `Completed · ${reply.milliseconds.toFixed(2)} ms shaping · one shaping call.`);
  }

  function invoke() {
    clearTimeout(timer);
    const id = ++request;
    if (!loaded) return;
    let invalid = false;
    for (const input of inputs) {
      try { parseInteger(input.value); input.setAttribute('aria-invalid', 'false'); }
      catch { input.setAttribute('aria-invalid', 'true'); invalid = true; }
    }
    if (invalid) {
      state('error', 'Enter a whole number for every argument. Decimal, hexadecimal (0x), and binary (0b) are supported.');
      return;
    }
    state('running', 'Running the font…');
    worker.postMessage({id, action: 'run', args: inputs.map(input => input.value), enabled: element('enabled').checked});
  }

  function edited() {
    ++request; // Never display a result from before this edit.
    clearTimeout(timer);
    if (loaded) {
      state('pending', 'Arguments changed. Running the font…');
      timer = setTimeout(invoke, 220);
    }
  }

  async function loadProgram(example, bytes, abi, current) {
    if (current !== generation) return;
    manifest = abi;
    resultLabels = example.result_labels || [];
    inputs = [];
    parameters.replaceChildren();
    for (const [index, type] of manifest.parameter_types.entries()) {
      const field = doc.createElement('div'), label = doc.createElement('label');
      const input = doc.createElement('input');
      input.id = `argument-${index}`; input.type = 'text'; input.spellcheck = false;
      input.autocomplete = 'off'; input.value = example.arguments?.[index] ?? '0';
      input.setAttribute('aria-describedby', 'argument-help');
      label.htmlFor = input.id;
      label.textContent = `${example.parameters?.[index] || 'Argument ' + (index + 1)} · ${type}`;
      input.addEventListener('input', edited);
      field.append(label, input); parameters.append(field); inputs.push(input);
    }
    if (!inputs.length) parameters.textContent = 'This function takes no arguments.';
    element('description').textContent = example.description;
    element('source-label').textContent = `${example.language || 'Program'} source${abi.export ? ' · export ' + abi.export : ''}`;
    element('source').textContent = example.source || 'Source is not included in this font/manifest pair.';
    const metrics = abi.metrics || {};
    element('metrics').textContent = `${abi.parameter_types.join(', ') || 'no arguments'} → ${abi.result_types.join(', ') || 'no return values'} · ${abi.tape.length.toLocaleString()} registers${metrics.lookups ? ' · ' + metrics.lookups.toLocaleString() + ' lookups' : ''}`;
    if (metrics.lookup_batch_size > 1) {
      element('metrics').textContent += ` · ${metrics.gate_groups.toLocaleString()} gate groups · up to ${metrics.lookup_batch_size} groups per lookup`;
    }
    if (metrics.coalesced_gate_groups > 0) {
      element('metrics').textContent += ` · ${metrics.gate_subtables.toLocaleString()} gate subtables after sharing`;
    }
    element('downloads').hidden = !example.font;
    if (example.font) {
      for (const [id, name] of [['font-download', example.font], ['manifest-download', example.manifest], ['wasm-download', example.module]]) {
        element(id).href = new URL(name, assets).href;
      }
    }
    worker = new Worker(new URL('./worker.mjs', import.meta.url), {type: 'module'});
    worker.onerror = () => {
      if (current !== generation) return;
      loaded = false;
      worker.terminate();
      state('error', 'The shaping engine could not load. Serve the repository root with python3 -m http.server 8000 and open this page on localhost.');
    };
    worker.onmessage = ({data}) => {
      if (current !== generation) return;
      if (data.action === 'load') {
        if (data.error) { loaded = false; state('error', errorMessage(data.error)); return; }
        loaded = true;
        element('metrics').textContent += ` · HarfBuzz ${data.version}`;
        invoke();
      } else if (data.id === request) {
        if (data.error) state('error', errorMessage(data.error));
        else showResult(data);
      }
    };
    worker.postMessage({id: ++request, action: 'load', bytes, manifest}, [bytes]);
  }

  function beginLoad() {
    ++generation; ++request; clearTimeout(timer);
    worker?.terminate(); worker = undefined; loaded = false; manifest = undefined;
    parameters.replaceChildren(); inputs = [];
    element('downloads').hidden = true;
    element('source').textContent = '';
    element('description').textContent = '';
    element('metrics').textContent = '';
    state('loading', 'Loading the program font…');
    return generation;
  }

  async function response(url) {
    const result = await fetch(url);
    if (!result.ok) throw new Error(`Could not load ${url.pathname.split('/').pop()}. Serve the repository root with python3 -m http.server 8000.`);
    return result;
  }

  async function loadExample() {
    const example = select.value === 'custom' ? customProgram?.example : catalog.find(item => item.id === select.value);
    if (!example) return;
    const current = beginLoad();
    try {
      if (select.value === 'custom') {
        await loadProgram(example, customProgram.bytes.slice(0), customProgram.abi, current);
        return;
      }
      const [fontResponse, manifestResponse] = await Promise.all([
        response(new URL(example.font, assets)), response(new URL(example.manifest, assets))]);
      const [bytes, abi] = await Promise.all([fontResponse.arrayBuffer(), manifestResponse.json()]);
      await loadProgram(example, bytes, abi, current);
    } catch (error) { if (current === generation) state('error', errorMessage(error)); }
  }

  element('invocation').addEventListener('submit', event => { event.preventDefault(); invoke(); });
  element('enabled').addEventListener('change', invoke);
  select.addEventListener('change', loadExample);
  element('files').addEventListener('change', async event => {
    const current = beginLoad();
    try {
      const files = [...event.target.files];
      const ttf = files.find(file => /\.ttf$/i.test(file.name));
      const json = files.find(file => /\.json$/i.test(file.name));
      if (files.length !== 2 || !ttf || !json) throw new Error('Select one .ttf font and its matching .json manifest together.');
      if (ttf.size > 32 * 1024 * 1024 || json.size > 10 * 1024 * 1024) throw new Error('Use a font under 32 MB and a manifest under 10 MB.');
      const [bytes, abi] = await Promise.all([ttf.arrayBuffer(), json.text().then(JSON.parse)]);
      registerLayout(abi);
      if (current !== generation) return;
      const example = {description: 'Your compiled program. Change its arguments to run the font.'};
      customProgram = {example, bytes: bytes.slice(0), abi};
      let option = select.querySelector('[value="custom"]');
      if (!option) { option = doc.createElement('option'); option.value = 'custom'; select.append(option); }
      option.textContent = ttf.name; select.value = 'custom';
      await loadProgram(example, bytes, abi, current);
    } catch (error) { if (current === generation) state('error', errorMessage(error)); }
    event.target.value = '';
  });

  const ready = (async () => {
    try {
      catalog = await (await response(new URL('catalog.json', assets))).json();
      select.replaceChildren();
      catalog.forEach(example => {
        const option = doc.createElement('option'); option.value = example.id; option.textContent = example.title; select.append(option);
      });
      select.disabled = false;
      await loadExample();
    } catch (error) { state('error', errorMessage(error)); }
  })();
  return {ready};
}

if (typeof document !== 'undefined') createPlayground();
