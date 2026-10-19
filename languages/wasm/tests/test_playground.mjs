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
    if (entry.id === 'c-array' || entry.id === 'c-sparse-array') {
      for (const count of ['0', '1', '2', '3', '4', '5', '-1']) {
        for (const bias of ['0', '10', '-1', '2147483648', '4294967295']) cases.push([count, bias]);
      }
      if (entry.id === 'c-array') assert.equal(manifest.limits.memory_base, 65536);
      else assert.deepEqual(manifest.limits.memory_regions, [[65024, 16], [65536, 16]]);
      assert.deepEqual(font.invoke(entry.arguments).results.map(value => value.unsigned), ['66']);
      assert.deepEqual(font.invoke(entry.arguments).results.map(value => value.unsigned), ['66']);
      assert.throws(() => font.invoke(['5', '0']), {name: 'WasmTrap', message: 'unreachable'});
      assert.throws(() => font.invoke(entry.arguments, false), {name: 'IncompleteShaping'});
    }
    else if (entry.id === 'sum_loop' || entry.id === 'recursive_sum') cases.push(['0'], ['1'], ['7']);
    else if (entry.id === 'division_loop64') {
      cases.push(['100', '7', '0'], ['100', '7', '3'], ['-1', '7', '7'],
        ['-1', '1', '7'], ['1', '0', '0'], ['1', '0', '7']);
      assert.throws(() => font.invoke(['100', '7', '8']), {name: 'ExecutionBoundExceeded', message: 'loop'});
      assert.throws(() => font.invoke(entry.arguments, false), {name: 'IncompleteShaping'});
      assert.deepEqual(font.invoke(['100', '7', '3']).results.map(value => value.unsigned), ['23', '5']);
    }
    else if (entry.id === 'memory_roundtrip') cases.push(['0', '-1'], ['12', '2147483648']);
    else if (entry.id === 'indirect64') {
      for (const index of ['0', '1', '2', '3', '4', '5', '6', '-1']) {
        cases.push(['18446744073709551615', '7', index], ['100', '0', index]);
      }
      for (const [index, reason] of [['4', 'indirect_call_type_mismatch'],
          ['5', 'uninitialized_element'], ['6', 'table_out_of_bounds']]) {
        assert.throws(() => font.invoke(['1', '0', index]), {name: 'WasmTrap', message: reason});
      }
      assert.throws(() => font.invoke(entry.arguments, false), {name: 'IncompleteShaping'});
      assert.deepEqual(font.invoke(entry.arguments).results.map(value => value.unsigned), ['14', '3']);
    }
    else if (entry.id === 'start_memory') {
      cases.push(['0', '0'], ['15', '-1'], ['7', '0x123'], ['3', '0xaa'], ['65536', '0'], ['-1', '0']);
      assert.throws(() => font.invoke(['16', '0']), {name: 'ExecutionBoundExceeded', message: 'memory'});
      assert.throws(() => font.invoke(['65535', '0']), {name: 'ExecutionBoundExceeded', message: 'memory'});
      assert.throws(() => font.invoke(entry.arguments, false), {name: 'IncompleteShaping'});
      assert.deepEqual(font.invoke(entry.arguments).results.map(value => value.hex),
        ['0x08070605aa030201', '0x100f0e0d0c0b0a09', '0x00000001', '0x00000001']);
    }
    else if (entry.id === 'c-callbacks') {
      for (const operation of ['0', '1', '2', '3', '-1']) {
        for (const [a, b] of [['100', '7'], ['-1', '1'], ['1', '0'], ['0', '0'], ['9223372036854775808', '-1']]) {
          cases.push([a, b, operation]);
        }
      }
      assert.throws(() => font.invoke(['1', '0', '2']), {name: 'WasmTrap', message: 'integer_divide_by_zero'});
      assert.throws(() => font.invoke(['1', '0', '3']), {name: 'WasmTrap', message: 'unreachable'});
      assert.throws(() => font.invoke(entry.arguments, false), {name: 'IncompleteShaping'});
      assert.deepEqual(manifest.limits.memory_regions, [[65536, 12]]);
      assert.deepEqual(font.invoke(entry.arguments).results.map(value => value.unsigned), ['14']);
    }
    else if (entry.id === 'c-packet') {
      for (const count of ['0', '1', '3', '7', '8', '-1']) {
        for (const adjustment of ['0', '10', '255', '256', '-1', '2147483648']) cases.push([count, adjustment]);
      }
      assert.deepEqual(manifest.limits.memory_regions, [[65504, 8], [65536, 8]]);
      assert.deepEqual(font.invoke(entry.arguments).results.map(value => value.unsigned), ['1610677118']);
      assert.deepEqual(font.invoke(entry.arguments).results.map(value => value.unsigned), ['1610677118']);
      assert.throws(() => font.invoke(entry.arguments, false), {name: 'IncompleteShaping'});
    }
    else if (entry.id === 'reference_flow') {
      for (const slot of ['0', '1', '2', '3', '-1']) {
        for (const enabled of ['0', '1']) {
          cases.push(['100', '7', slot, enabled], ['1', '0', slot, enabled]);
        }
      }
      assert.throws(() => font.invoke(['100', '7', '1', '1']), {name: 'WasmTrap', message: 'uninitialized_element'});
      assert.throws(() => font.invoke(['100', '7', '3', '0']), {name: 'WasmTrap', message: 'table_out_of_bounds'});
      assert.deepEqual(font.invoke(entry.arguments).results.map(value => value.unsigned), ['14', '3']);
      assert.deepEqual(font.invoke(['100', '7', '1', '0']).results.map(value => value.unsigned), ['107', '5']);
      assert.throws(() => font.invoke(entry.arguments, false), {name: 'IncompleteShaping'});
    }
    else if (entry.id === 'indexed_memory') {
      for (let offset = 0; offset < 64; offset++) {
        for (const seed of ['0', '-1', '0x0807060504030201']) cases.push([String(offset), seed]);
      }
      cases.push(['65536', '0'], ['-1', '0']);
      assert.throws(() => font.invoke(['64', '0']), {name: 'ExecutionBoundExceeded', message: 'memory'});
      assert.throws(() => font.invoke(['65535', '0']), {name: 'ExecutionBoundExceeded', message: 'memory'});
      assert.throws(() => font.invoke(entry.arguments, false), {name: 'IncompleteShaping'});
      assert.deepEqual(font.invoke(entry.arguments).results.map(value => value.unsigned), ['3', '13']);
    }
    else if (entry.id === 'mutable_dispatch') {
      for (const operation of ['0', '1', '2', '-1']) {
        for (const [a, b] of [['100', '7'], ['-1', '1'], ['1', '0'], ['0', '-1']]) {
          cases.push([a, b, operation]);
        }
      }
      assert.throws(() => font.invoke(['1', '0', '1']), {name: 'WasmTrap', message: 'integer_divide_by_zero'});
      assert.throws(() => font.invoke(['1', '1', '2']), {name: 'WasmTrap', message: 'table_out_of_bounds'});
      assert.throws(() => font.invoke(entry.arguments, false), {name: 'IncompleteShaping'});
      assert.deepEqual(font.invoke(entry.arguments).results.map(value => value.unsigned), ['14', '3', '3']);
      assert.deepEqual(font.invoke(entry.arguments).results.map(value => value.unsigned), ['14', '3', '3']);
    }
    else if (entry.id === 'memory_grow') {
      cases.push(['0', '0', '0'], ['1', '1', '-1'], ['3', '1', '42'],
        ['-1', '2', '0x8000000000000000'], ['2', '1', '7'], ['1', '-1', '13']);
      assert.throws(() => font.invoke(entry.arguments, false), {name: 'IncompleteShaping'});
      assert.deepEqual(font.invoke(entry.arguments).results.map(value => value.unsigned),
        ['1', '4294967295', '2', '9920249030613615975']);
    }
    else if (entry.id === 'passive_data') {
      cases.push(['0', '0', '16', '0'], ['2', '1', '8', '0'], ['15', '15', '1', '0'],
        ['65536', '16', '0', '0'], ['65536', '0', '0', '1'],
        ['0', '0', '1', '1'], ['0', '1', '0', '1'], ['0', '16', '1', '0'],
        ['65535', '0', '2', '0'], ['0', '4294967295', '1', '0']);
      assert.throws(() => font.invoke(['16', '0', '1', '0']),
        {name: 'ExecutionBoundExceeded', message: 'memory'});
      assert.throws(() => font.invoke(['16', '16', '1', '0']),
        {name: 'WasmTrap', message: 'memory_out_of_bounds'});
      assert.throws(() => font.invoke(entry.arguments, false), {name: 'IncompleteShaping'});
      assert.deepEqual(font.invoke(entry.arguments).results.map(value => value.hex),
        ['0x0c0b0a0908070605', '0x0000000000000000']);
    }
    else if (entry.id === 'bulk_memory') {
      for (const [destination, source, length] of [['0', '2', '8'], ['0', '0', '16'],
          ['16', '16', '0'], ['65536', '65536', '0'], ['65535', '0', '2'],
          ['0', '65535', '2'], ['4294967295', '0', '1'], ['0', '0', '4294967295']]) {
        cases.push(['0xfedcba9876543210', destination, source, length, '-1']);
      }
      assert.throws(() => font.invoke(['1', '16', '0', '1', '0']),
        {name: 'ExecutionBoundExceeded', message: 'memory'});
      assert.throws(() => font.invoke(['1', '0', '16', '1', '0']),
        {name: 'ExecutionBoundExceeded', message: 'memory'});
      assert.throws(() => font.invoke(entry.arguments, false), {name: 'IncompleteShaping'});
      assert.deepEqual(font.invoke(entry.arguments).results.map(value => value.hex),
        ['0x0605040302010201', '0xaaaaaaaaaaaa0807']);
    }
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
