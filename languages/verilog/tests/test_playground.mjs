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
const signed8 = value => Number(BigInt.asIntN(8, BigInt(value)));
const expected = {
  population_count: a => [a.toString(2).replaceAll('0','').length],
  generated_xor: (a,b) => [a^b],
  array_lookup: (a,b,index) => index<4 ? [[a,b,a^b,(~a)&255][index]] : null,
  division: (a,b) => {
    a=signed8(a); b=signed8(b);
    if (!b) return null;
    const q=Math.trunc(a/b), r=a-q*b, unsignedA=a&255, unsignedB=b&255;
    return [q&255,r&255,Math.floor(unsignedA/unsignedB),unsignedA%unsignedB];
  },
  signed_math: (a,b,n) => {
    a=signed8(a); b=signed8(b);
    return [(a+b)&511,(a*b)&65535,(a>>n)&255,Number(a<b)];
  },
  procedural_alu: (a,b,op) => [[(a+b)&511,(a-b)&511,a^b,((a&15)<<4)|(b&15)][op]],
  hierarchical_adder: (a,b) => [a+b],
  dynamic_routes: (data,index,value) => {
    if (index>=8) return null;
    let patched=data;
    for (let i=0; i<3 && index+i<8; i++) patched=(patched&~(1<<(index+i)))|(((value>>i)&1)<<(index+i));
    return [(data>>index)&1,index<=5 ? (data>>index)&7 : 0,patched];
  },
  adder: (a,b) => [a+b],
  alu: (a,b,op) => [[a+b,a-b,a^b,b>=8 ? 0 : a<<b][op]&255, Number(a===b), Number(a<b)],
  multiplier: (a,b) => [a*b],
  bit_routes: (a,en) => [((a&15)<<4)|(a>>4), en ? a : 0, a.toString(2).replaceAll('0','').length%2, Number(a===255)],
  parameter_adder: (a,b) => [a+b,(a^b)&0xa5,a^0x80],
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
      if (expected[entry.id](...args) === null) {
        assert.throws(() => font.invoke(args.map(String)), {name:'WasmTrap',message:entry.id==='division' ? 'integer_divide_by_zero' : entry.id==='array_lookup' ? 'invalid_array_index' : 'invalid_select'});
        continue;
      }
      const shaped = font.invoke(args.map(String));
      assert.deepEqual(shaped.results.map(result => Number(result.unsigned)), expected[entry.id](...args));
      shaped.results.forEach((result,i) => {
        assert.equal(result.binary.length, manifest.outputs[i].width);
        if (manifest.outputs[i].signed) {
          assert.equal(result.signed, String(BigInt.asIntN(manifest.outputs[i].width, BigInt(expected[entry.id](...args)[i]))));
        }
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
      {outputs:[{name:'sum',width:'9',signed:false}]},
      {inputs:[{name:'bad name',width:8},{name:'b',width:8}]}]) {
    assert.throws(() => validateVerilog({...manifest,...update}), /Verilog/);
  }
  for (const type of ['i0','i65','f32','i01',null,3]) {
    assert.throws(() => registerLayout({...manifest, parameter_types:[type,'i8']}), /ABI manifest/);
  }
});

test('parameter metadata preserves full-width integers and rejects malformed values', async () => {
  const manifest = JSON.parse(await readFile(new URL('parameter_adder.json', assets)));
  validateVerilog(manifest);
  const parameter = {name:'MASK',value:'18446744073709551615',width:64,signed:false,local:false};
  validateVerilog({...manifest,parameters:[parameter]});
  for (const update of [{value:18446744073709551615}, {value:'18446744073709551616'},
      {value:'-1'}, {width:65}, {signed:1}, {local:undefined}, {name:'bad name'}, {value:'0xff'}]) {
    assert.throws(() => validateVerilog({...manifest,parameters:[{...parameter,...update}]}), /parameter metadata/);
  }
  assert.throws(() => validateVerilog({...manifest,parameters:[parameter,parameter]}), /parameter metadata/);
});


test('signed port metadata is required for v2 and legacy unsigned manifests remain valid', async () => {
  const manifest = JSON.parse(await readFile(new URL('signed_math.json', assets)));
  for (const signed of [undefined,null,0,1,'true']) {
    const outputs=manifest.outputs.map(port => ({...port}));
    outputs[0].signed=signed;
    assert.throws(() => validateVerilog({...manifest,outputs}), /port metadata/);
  }
  const legacy=JSON.parse(await readFile(new URL('adder.json', assets)));
  legacy.verilog_subset='unsigned-combinational-v1';
  for (const port of [...legacy.inputs,...legacy.outputs]) delete port.signed;
  validateVerilog(legacy);
  legacy.outputs[0].signed=true;
  assert.throws(() => validateVerilog(legacy), /port metadata/);
});


test('instance metadata validates named paths and specialized constants', async () => {
  const manifest=JSON.parse(await readFile(new URL('hierarchical_adder.json',assets)));
  validateVerilog(manifest);
  const instance=manifest.hierarchy[0];
  for (const update of [{path:'bad path'},{path:1},{module:'bad module'},{parameters:null},
      {parameters:[{name:'W',value:'16',width:4,signed:false,local:false}]}]) {
    assert.throws(() => validateVerilog({...manifest,hierarchy:[{...instance,...update}]}), /metadata/);
  }
  assert.throws(() => validateVerilog({...manifest,hierarchy:[instance,instance]}), /hierarchy metadata/);
  assert.throws(() => validateVerilog({...manifest,hierarchy:new Array(128).fill(instance)}), /hierarchy metadata/);
});


test('generated instance paths allow bounded array indices', async () => {
  const manifest=JSON.parse(await readFile(new URL('generated_xor.json',assets)));
  validateVerilog(manifest);
  const instance=manifest.hierarchy[0];
  validateVerilog({...manifest,hierarchy:[{...instance,path:'rows[-1].lanes[3].u'}]});
  for (const path of ['lanes[].u','lanes[abc].u','lanes[1.5].u','lanes[0]..u','lanes[0].']) {
    assert.throws(() => validateVerilog({...manifest,hierarchy:[{...instance,path}]}), /hierarchy metadata/);
  }
});
