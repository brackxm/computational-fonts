// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
import {parseInteger, registerLayout} from '../../shared/playground/runtime.mjs';

export function validateVerilog(manifest) {
  registerLayout(manifest);
  if (manifest.language !== 'verilog' || manifest.verilog_subset !== 'unsigned-combinational-v1') {
    throw new Error('Select a compiled Verilog font and its matching manifest.');
  }
  for (const [ports, types] of [[manifest.inputs, manifest.parameter_types], [manifest.outputs, manifest.result_types]]) {
    if (!Array.isArray(ports) || ports.length !== types.length || ports.some((port, i) =>
      !port || typeof port.name !== 'string' || !/^[a-zA-Z_][a-zA-Z_0-9$]*$/.test(port.name) ||
      !Number.isInteger(port.width) || types[i] !== `i${port.width}`)) throw new Error('Invalid Verilog port metadata.');
  }
}

export function createPlayground(doc = document) {
  const $ = id => doc.getElementById(id);
  const assets = new URL('./assets/', import.meta.url);
  let catalog = [], worker, manifest, fields = [], ready = false;
  let generation = 0, request = 0, timer;

  function state(kind, message) {
    $('status').dataset.state = kind;
    $('status').textContent = message;
    $('run').disabled = !ready || kind === 'running';
    if (kind !== 'ready') $('results').replaceChildren();
  }

  function invoke() {
    clearTimeout(timer);
    if (!ready) return;
    const id = ++request;
    try {
      for (const field of fields) {
        try { parseInteger(field.value); field.setAttribute('aria-invalid', 'false'); }
        catch (error) { field.setAttribute('aria-invalid', 'true'); throw error; }
      }
      state('running', 'Computing circuit outputs in the font…');
      worker.postMessage({id, action: 'run', args: fields.map(field => field.value), enabled: $('enabled').checked});
    } catch (error) { state('error', error.message); }
  }

  function edited() {
    ++request;
    clearTimeout(timer);
    if (ready) {
      state('pending', 'Inputs changed. Running the font…');
      timer = setTimeout(invoke, 220);
    }
  }

  function beginLoad() {
    ++generation; ++request; clearTimeout(timer);
    worker?.terminate(); worker = undefined; ready = false;
    fields = []; $('parameters').replaceChildren();
    $('source').textContent = ''; $('metrics').textContent = '';
    $('description').textContent = ''; $('downloads').hidden = true;
    state('loading', 'Loading the circuit font…');
    return generation;
  }

  async function load(bytes, abi, example, current) {
    if (current !== generation) return;
    validateVerilog(abi);
    manifest = abi;
    for (const [i, port] of abi.inputs.entries()) {
      const field = doc.createElement('input'), label = doc.createElement('label'), box = doc.createElement('div');
      field.id = `input-${i}`; field.type = 'text'; field.autocomplete = 'off'; field.spellcheck = false;
      field.value = example.arguments?.[i] ?? '0';
      field.setAttribute('aria-describedby', 'input-help');
      label.htmlFor = field.id; label.textContent = `${port.name} · ${port.width} bit${port.width === 1 ? '' : 's'}`;
      field.addEventListener('input', edited); box.append(label, field); $('parameters').append(box); fields.push(field);
    }
    if (!fields.length) $('parameters').textContent = 'This circuit has no input ports.';
    $('description').textContent = example.description || `Module ${abi.module}. Change input ports to run the font.`;
    $('source').textContent = typeof abi.source === 'string' ? abi.source : 'Source not included.';
    $('metrics').textContent = `${abi.module} · ${abi.metrics?.gates ?? '?'} Boolean gates · ${abi.tape.length} registers · one shaping call`;
    if (example.font) {
      $('downloads').hidden = false;
      $('font-download').href = new URL(example.font, assets).href;
      $('manifest-download').href = new URL(example.manifest, assets).href;
    }
    worker = new Worker(new URL('../../shared/playground/worker.mjs', import.meta.url), {type: 'module'});
    worker.onerror = () => {
      if (current !== generation) return;
      ready = false; worker.terminate();
      state('error', 'The shaping engine could not load. Serve the repository root on localhost.');
    };
    worker.onmessage = ({data}) => {
      if (current !== generation) return;
      if (data.action === 'load') {
        if (data.error) { state('error', data.error.message); return; }
        ready = true; invoke(); return;
      }
      if (data.id !== request) return;
      if (data.error) { state('error', data.error.message); return; }
      $('results').replaceChildren();
      data.results.forEach((result, i) => {
        const card = doc.createElement('section'), title = doc.createElement('h2');
        const number = doc.createElement('div'), bits = doc.createElement('p');
        card.className = 'result'; number.className = 'number'; bits.className = 'bits';
        title.textContent = `${manifest.outputs[i].name} · ${manifest.outputs[i].width} bits · unsigned`;
        number.textContent = result.unsigned; bits.textContent = `${result.hex} · ${result.binary}`;
        card.append(title, number, bits); $('results').append(card);
      });
      state('ready', `Computed · ${data.milliseconds.toFixed(2)} ms shaping · one shaping call.`);
    };
    worker.postMessage({id: ++request, action: 'load', bytes, manifest}, [bytes]);
  }

  async function fetchAsset(name, format) {
    const response = await fetch(new URL(name, assets));
    if (!response.ok) throw new Error(`Could not load ${name}. Serve the repository root on localhost.`);
    return response[format]();
  }

  $('example').addEventListener('change', async () => {
    const current = beginLoad();
    try {
      const example = catalog.find(item => item.id === $('example').value);
      const [bytes, abi] = await Promise.all([fetchAsset(example.font, 'arrayBuffer'), fetchAsset(example.manifest, 'json')]);
      await load(bytes, abi, example, current);
    } catch (error) { if (current === generation) state('error', error.message); }
  });
  $('files').addEventListener('change', async event => {
    const current = beginLoad();
    try {
      const files = [...event.target.files];
      const ttf = files.find(file => /\.ttf$/i.test(file.name)), json = files.find(file => /\.json$/i.test(file.name));
      if (files.length !== 2 || !ttf || !json) throw new Error('Select one .ttf font and its matching .json manifest together.');
      if (ttf.size > 32*1024*1024 || json.size > 10*1024*1024) throw new Error('Use a font under 32 MB and a manifest under 10 MB.');
      const [bytes, abi] = await Promise.all([ttf.arrayBuffer(), json.text().then(JSON.parse)]);
      if (current !== generation) return;
      $('example').selectedIndex = -1;
      await load(bytes, abi, {}, current);
    } catch (error) { if (current === generation) state('error', error.message); }
    event.target.value = '';
  });
  $('invocation').addEventListener('submit', event => { event.preventDefault(); invoke(); });
  $('enabled').addEventListener('change', invoke);
  const initialized = (async () => {
    try {
      catalog = await fetchAsset('catalog.json', 'json');
      $('example').replaceChildren();
      for (const example of catalog) {
        const option = doc.createElement('option'); option.value = example.id; option.textContent = example.title;
        $('example').append(option);
      }
      $('example').disabled = false;
      $('example').dispatchEvent(new Event('change'));
    } catch (error) { state('error', error.message); }
  })();
  return {initialized};
}

if (typeof document !== 'undefined') createPlayground();
