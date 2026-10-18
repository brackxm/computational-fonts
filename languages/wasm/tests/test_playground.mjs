// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import * as hb from '../../shared/vendor/harfbuzzjs/index.mjs';
import {RegisterFont, parseInteger, registerLayout} from '../../shared/playground/runtime.mjs';

const assets = new URL('../playground/assets/', import.meta.url);
const catalog = JSON.parse(await readFile(new URL('catalog.json', assets)));
const fixture = async id => {
  const entry = catalog.find(item => item.id === id);
  const bytes = await readFile(new URL(entry.font, assets));
  const manifest = JSON.parse(await readFile(new URL(entry.manifest, assets)));
  return {entry, bytes, manifest, font: await RegisterFont.create(hb, bytes, manifest)};
};

test('integer arguments preserve all 64 bits and accept signed base prefixes', () => {
  assert.equal(parseInteger('18446744073709551615'), (1n << 64n) - 1n);
  assert.equal(parseInteger('-0x8000000000000000'), -(1n << 63n));
  assert.equal(parseInteger('+0B1010'), 10n);
  for (const value of ['', '1.5', '1e3', '0x', '1n', '12x', '1 2', 'Infinity', '9'.repeat(1025)]) {
    assert.throws(() => parseInteger(value), /whole number/);
  }
});

for (const entry of catalog) {
  test(`${entry.id}: browser HarfBuzz results agree with fresh V8 instances`, async () => {
    const {font, manifest} = await fixture(entry.id);
    const module = await WebAssembly.compile(await readFile(new URL(entry.module, assets)));
    const cases = [entry.arguments];
    if (entry.id === 'sum_loop' || entry.id === 'recursive_sum') cases.push(['0'], ['1'], ['7']);
    else if (entry.id === 'memory_roundtrip') cases.push(['0', '-1'], ['12', '2147483648']);
    else if (['three_divs64', 'four_divs64'].includes(entry.id)) {
      const four = entry.id === 'four_divs64';
      cases.push(Array.from({length: four ? 8 : 6}, (_, i) => i % 2 ? '1' : '-1'));
      cases.push(['9223372036854775808', '3', '9223372036854775807', '7', '-1', '11',
        ...(four ? ['1', '18446744073709551615'] : [])]);
      for (const divisor of four ? [1, 3, 5, 7] : [1, 3, 5]) {
        const zero = [...entry.arguments]; zero[divisor] = '0'; cases.push(zero);
      }
      if (four) {
        assert.ok(manifest.metrics.gate_groups > 16000);
        assert.ok(manifest.metrics.gate_subtables < 10000);
        assert.ok(manifest.metrics.coalesced_gate_groups > 15000);
      } else assert.ok(manifest.metrics.lookup_batch_size > 16);
      assert.ok(manifest.metrics.font_bytes < 32 * 1024 * 1024);
      assert.throws(() => font.invoke(entry.arguments, false), {name: 'IncompleteShaping'});
    }
    else if (['expensive64', 'divmul64', 'divmulcount64'].includes(entry.id)) {
      cases.push(['100', '3', '200', '7'], ['-17', '3', '17', '-3'],
        ['9223372036854775807', '1', '9223372036854775807', '1'],
        ['1', '0', '2', '1'], ['1', '1', '2', '0'],
        ['-9223372036854775808', '-1', '2', '1'], ['1', '1', '-9223372036854775808', '-1']);
      if (entry.id === 'divmul64') cases.push(['18446744073709551615', '1', '18446744073709551615', '1']);
      assert.ok(manifest.metrics.gate_groups > 5400);
      assert.ok(manifest.metrics.lookups < 5400);
      assert.throws(() => font.invoke(entry.arguments, false), {name: 'IncompleteShaping'});
    }
    else if (entry.id.startsWith('divide64_dynamic')) {
      cases.push(['0', '1'], ['1', '0'], ['-9223372036854775808', '-1'],
        ['-9223372036854775808', '1'], ['-17', '3'], ['17', '-3'],
        ['18446744073709551615', '9223372036854775808']);
    }
    else {
      cases.push(manifest.parameter_types.map(() => '-1'), manifest.parameter_types.map(() => '0'));
      cases.push(manifest.parameter_types.map((type, i) => ((1n << BigInt(type.slice(1))) - BigInt(i + 1)).toString()));
    }
    for (const values of cases) {
      const instance = new WebAssembly.Instance(module);
      const args = values.map((value, i) => {
        const n = BigInt.asIntN(Number(manifest.parameter_types[i].slice(1)), parseInteger(value));
        return manifest.parameter_types[i] === 'i64' ? n : Number(n);
      });
      let reference;
      try { reference = instance.exports[manifest.export](...args); }
      catch (error) {
        assert.ok(error instanceof WebAssembly.RuntimeError);
        assert.throws(() => font.invoke(values), {name: 'WasmTrap'});
        continue;
      }
      const expected = reference === undefined ? [] : Array.isArray(reference) ? reference : [reference];
      const shaped = font.invoke(values);
      assert.deepEqual(shaped.results.map(result => result.unsigned), expected.map((value, i) =>
        BigInt.asUintN(Number(manifest.result_types[i].slice(1)), BigInt(value)).toString()));
      for (const result of shaped.results) assert.equal(result.binary.length, Number(result.type.slice(1)));
    }
  });
}

test('loops, calls and the backed memory window report bounds without plausible output', async () => {
  for (const [name, args, detail] of [['sum_loop', ['8'], 'loop'], ['recursive_sum', ['8'], 'call'],
      ['memory_roundtrip', ['13', '1'], 'memory']]) {
    const {font} = await fixture(name);
    assert.throws(() => font.invoke(args), {name: 'ExecutionBoundExceeded', message: detail});
  }
  const {font} = await fixture('memory_roundtrip');
  assert.throws(() => font.invoke(['65535', '1']), {name: 'WasmTrap', message: 'memory_out_of_bounds'});
  assert.equal(font.invoke(['3', '42']).results[0].unsigned, '42');
});

test('disabled shaping is rejected; enabling it again computes the actual result', async () => {
  const {font} = await fixture('compose');
  assert.throws(() => font.invoke(['123', '77'], false), {name: 'IncompleteShaping'});
  assert.equal(font.invoke(['123', '77']).results[0].unsigned, '230');
  const {font: divider} = await fixture('divide64_dynamic');
  assert.throws(() => divider.invoke(['18446744073709551615', '3'], false), {name: 'IncompleteShaping'});
  assert.deepEqual(divider.invoke(['18446744073709551615', '3']).results.map(value => value.unsigned),
    ['6148914691236517205', '0']);
});

test('mismatched fonts, malformed manifests and invalid arguments fail closed', async () => {
  const {bytes, manifest, font} = await fixture('compose');
  const wrongBytes = bytes.slice(); wrongBytes[0] ^= 1;
  await assert.rejects(RegisterFont.create(hb, wrongBytes, manifest), /does not match/);
  for (const update of [{abi: 'unknown'}, {results: [[999999]]}, {flags: {'trap.zero': 999999}},
      {parameter_types: ['f32']}, {tape: [{...manifest.tape[0], kind: 'unknown'}]}]) {
    assert.throws(() => registerLayout({...manifest, ...update}), /ABI manifest/);
  }
  assert.throws(() => font.invoke(['1']), /argument count/);
  assert.throws(() => font.invoke(['1.5', '2']), /whole number/);
});
