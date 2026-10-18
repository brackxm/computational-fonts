// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import * as hb from '../../shared/vendor/harfbuzzjs/index.mjs';
import {RegisterFont, registerLayout} from '../../shared/playground/runtime.mjs';
import {validateVerilog} from '../playground/controls.mjs';

const assets = new URL('../playground/assets/', import.meta.url);
const catalog = JSON.parse(await readFile(new URL('catalog.json', assets)));
const expected = {
  adder: (a,b) => [a+b],
  alu: (a,b,op) => [[a+b,a-b,a^b,b>=8 ? 0 : a<<b][op]&255, Number(a===b), Number(a<b)],
  multiplier: (a,b) => [a*b],
  bit_routes: (a,en) => [((a&15)<<4)|(a>>4), en ? a : 0, a.toString(2).replaceAll('0','').length%2, Number(a===255)],
};

for (const entry of catalog) {
  test(`${entry.id}: browser HarfBuzz computes output ports`, async () => {
    const bytes = await readFile(new URL(entry.font, assets));
    const manifest = JSON.parse(await readFile(new URL(entry.manifest, assets)));
    validateVerilog(manifest);
    const font = await RegisterFont.create(hb, bytes, manifest);
    let seed = 42;
    const random = () => {seed=(Math.imul(seed,1664525)+1013904223)>>>0; return seed;};
    const cases = [entry.arguments.map(Number), manifest.inputs.map(() => 0), manifest.inputs.map(port => 2**port.width-1)];
    for (let n=0; n<50; n++) cases.push(manifest.inputs.map(port => random() % 2**port.width));
    for (const args of cases) {
      const shaped = font.invoke(args.map(String));
      assert.deepEqual(shaped.results.map(result => Number(result.unsigned)), expected[entry.id](...args));
      shaped.results.forEach((result,i) => {
        assert.equal(result.binary.length, manifest.outputs[i].width);
        assert.equal(result.hex.length, 2 + Math.ceil(manifest.outputs[i].width/4));
      });
    }
    assert.throws(() => font.invoke(entry.arguments, false), {name:'IncompleteShaping'});
    const tampered = bytes.slice(); tampered[0] ^= 1;
    await assert.rejects(RegisterFont.create(hb, tampered, manifest), /does not match/);
  });
}

test('Verilog metadata and arbitrary register widths are validated', async () => {
  const manifest = JSON.parse(await readFile(new URL('adder.json', assets)));
  for (const update of [{language:'other'}, {inputs:[]}, {outputs:[{name:'sum',width:8}]},
      {outputs:[{name:'sum',width:'9'}]},
      {inputs:[{name:'bad name',width:8},{name:'b',width:8}]}]) {
    assert.throws(() => validateVerilog({...manifest,...update}), /Verilog/);
  }
  for (const type of ['i0','i65','f32','i01',null,3]) {
    assert.throws(() => registerLayout({...manifest, parameter_types:[type,'i8']}), /ABI manifest/);
  }
});
