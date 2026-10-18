// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0

// This harness only serializes inputs and decodes shaped registers. It never
// interprets language instructions or evaluates source programs in the browser.
export class FontExecutionError extends Error {
  constructor(kind, message) {
    super(message);
    this.name = kind;
  }
}

export function parseInteger(text) {
  const value = String(text).trim();
  const match = /^([+-]?)(0x[\da-f]+|0b[01]+|\d+)$/i.exec(value);
  if (!match || value.length > 1024) {
    throw new Error('Enter a whole number in decimal, hexadecimal (0x), or binary (0b).');
  }
  return (match[1] === '-' ? -1n : 1n) * BigInt(match[2]);
}

export function registerLayout(manifest) {
  const invalid = () => { throw new Error('Invalid or unsupported font ABI manifest.'); };
  if (!manifest || manifest.abi !== 'wasm-gsub-registers-v1' ||
      !Array.isArray(manifest.parameter_types) || !Array.isArray(manifest.result_types) ||
      !Array.isArray(manifest.results) || !Array.isArray(manifest.tape) ||
      !manifest.flags || typeof manifest.flags !== 'object' || Array.isArray(manifest.flags) ||
      !/^[a-f\d]{64}$/.test(manifest.font_sha256)) invalid();
  const types = [...manifest.parameter_types, ...manifest.result_types];
  // The shared register ABI also serves Verilog's arbitrary 1–64-bit ports.
  if (types.some(type => typeof type !== 'string' || !/^i([1-9]|[1-5][0-9]|6[0-4])$/.test(type)) ||
      manifest.results.length !== manifest.result_types.length ||
      manifest.tape.length > 32766) invalid();
  let glyph = 2, previous = -1;
  const wires = new Map();
  const layout = manifest.tape.map(entry => {
    if (!Number.isSafeInteger(entry.wire) || entry.wire <= previous ||
        !['argument', 'constant', 'gate'].includes(entry.kind)) invalid();
    previous = entry.wire;
    if (entry.kind === 'argument' && (!Number.isInteger(entry.argument) || entry.argument < 0 ||
        entry.argument >= manifest.parameter_types.length || !Number.isInteger(entry.bit) ||
        entry.bit < 0 || entry.bit >= Number(manifest.parameter_types[entry.argument].slice(1)))) invalid();
    if (entry.kind === 'constant' && ![0, 1].includes(entry.constant)) invalid();
    const cell = {entry, zero: glyph++, one: glyph++};
    if (entry.kind === 'gate') cell.uninitialized = glyph++;
    wires.set(entry.wire, cell);
    return cell;
  });
  if (glyph >= 65535) invalid();
  manifest.results.forEach((bits, i) => {
    if (!Array.isArray(bits) || bits.length !== Number(manifest.result_types[i].slice(1)) ||
        bits.some(wire => !wires.has(wire))) invalid();
  });
  if (Object.entries(manifest.flags).some(([name, wire]) =>
      !/^(trap|limit)\.[a-z_]+$/.test(name) || !wires.has(wire))) invalid();
  return layout;
}

export class RegisterFont {
  static async create(hb, bytes, manifest) {
    const layout = registerLayout(manifest);
    if (!globalThis.crypto?.subtle) throw new Error('Open the playground on localhost or HTTPS to verify fonts.');
    const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes));
    const hash = [...digest].map(value => value.toString(16).padStart(2, '0')).join('');
    if (hash !== manifest.font_sha256) throw new Error('The font does not match its ABI manifest. Load the matching TTF and JSON files.');
    return new RegisterFont(hb, bytes, manifest, layout);
  }

  constructor(hb, bytes, manifest, layout) {
    this.hb = hb;
    this.manifest = manifest;
    this.layout = layout;
    this.blob = new hb.Blob(bytes);
    this.face = new hb.Face(this.blob);
    this.font = new hb.Font(this.face);
    this.buffer = new hb.Buffer();
    // emit_font's v1 ABI assigns supplementary PUA characters and glyph IDs
    // in tape order. Check both the cmap and glyph names before trusting it.
    for (const {entry, zero, one, uninitialized} of layout) {
      for (const [value, gid] of [[0, zero], [1, one], ['u', uninitialized]]) {
        if (gid === undefined) continue;
        if (this.font.nominalGlyph(0xf0000 + gid - 2) !== gid ||
            this.font.glyphName(gid) !== `w${entry.wire}_${value}`) {
          throw new Error('The font register layout does not match its ABI manifest. Rebuild the font.');
        }
      }
    }
  }

  invoke(inputs, enabled = true) {
    const {hb, manifest, layout, buffer} = this;
    if (inputs.length !== manifest.parameter_types.length) throw new Error('Wrong argument count.');
    const args = inputs.map(parseInteger);
    const codepoints = layout.map(({entry, zero, one, uninitialized}) => {
      const bit = entry.kind === 'argument' ? Number((args[entry.argument] >> BigInt(entry.bit)) & 1n) : entry.constant;
      const gid = entry.kind === 'gate' ? uninitialized : bit ? one : zero;
      return 0xf0000 + gid - 2;
    });
    buffer.reset();
    buffer.addCodePoints(codepoints);
    buffer.setDirection(hb.Direction.LTR);
    buffer.guessSegmentProperties();
    const start = performance.now();
    hb.shape(this.font, buffer, [new hb.Feature('calt', Number(enabled))]);
    const milliseconds = performance.now() - start;
    const glyphs = buffer.getGlyphInfos();
    if (glyphs.length !== layout.length) throw new FontExecutionError('IncompleteShaping', 'Shaping changed the register tape length.');
    const bits = new Map();
    layout.forEach(({entry, zero, one}, i) => {
      const gid = glyphs[i].codepoint;
      if (gid !== zero && gid !== one) {
        throw new FontExecutionError('IncompleteShaping', `Register ${entry.wire} is uninitialized. Enable font computation and use a compatible font.`);
      }
      const bit = Number(gid === one);
      if (entry.kind === 'constant' && bit !== entry.constant) throw new FontExecutionError('IncompleteShaping', 'A constant register was changed.');
      bits.set(entry.wire, bit);
    });
    for (const [name, wire] of Object.entries(manifest.flags)) {
      if (bits.get(wire)) {
        const [kind, detail] = name.split('.');
        throw new FontExecutionError(kind === 'trap' ? 'WasmTrap' : 'ExecutionBoundExceeded', detail);
      }
    }
    const results = manifest.results.map((wires, i) => {
      const binary = wires.map(wire => bits.get(wire)).reverse().join('');
      const unsigned = BigInt('0b' + binary);
      const width = Number(manifest.result_types[i].slice(1));
      return {type: manifest.result_types[i], unsigned: unsigned.toString(),
        signed: BigInt.asIntN(width, unsigned).toString(),
        hex: '0x' + unsigned.toString(16).padStart(Math.ceil(width / 4), '0'), binary};
    });
    return {results, milliseconds, registers: layout.length};
  }
}
