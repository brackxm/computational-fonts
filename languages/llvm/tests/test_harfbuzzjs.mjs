// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
// Independent HarfBuzzJS execution through the unmodified shared register ABI.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import * as hb from '../../shared/vendor/harfbuzzjs/index.mjs';
import {RegisterFont} from '../../shared/playground/runtime.mjs';

const assets = new URL('../fonts/', import.meta.url);
const octets = values => values.flatMap(n => Array.from({length:8}, (_,i) => String((n >> BigInt(i*8)) & 255n)));
const cases = {
  max: [[['-5','-2'],'4294967294'], [['2147483648','2147483647'],'2147483647']],
  clang_max: [[['-9','7'],'7']],
  clang_mix: [[['10','20'],'93']],
  clang_indexed: [[['2','100'],'111'], [['3','100'],'103']],
  clang_loop: [[['5'],'10']],
  loop: [[['0'],'0'], [['6'],'15']],
  memory: [[['3','4276993775'],'4276993775']],
  rust_max: [[['-7','4'],'4']],
  rust_mix: [[['2','3'],'643']],
  clang_lookup: [[['2'],'7'],[['4294967295'],'11']],
  clang_copied: [[['2','100'],'110']],
  clang_checked_add: [[['4294967295','1'],'4294967296'],[['12','30'],'42']],
  clang_checked_mul: [[['2147483647','2'],'8589934590']],
  rust_lookup: [[['2'],'7'],[['4294967295'],'11']],
  rust_checked_add: [[['4294967295','1'],'4294967296'],[['12','30'],'42']],
  rust_checked_mul: [[['2147483647','2'],'8589934590']],
  clang_sat_add: [[['4294967295','1'],'4294967295']],
  clang_sat_sub: [[['-2147483648','1'],'2147483648']],
  clang_global_calls: [[['1','100'],'108'],[['1','100'],'108']],
  clang_pointer_table: [[['1','100'],'111'],[['0','0'],'11']],
  clang_pointer_copy: [[['1','100'],'101'],[['0','100'],'100']],
  rust_sat_add: [[['4294967295','1'],'4294967295']],
  rust_sat_sub: [[['-2147483648','1'],'2147483648']],
  rust_global_calls: [[['1','100'],'108'],[['1','100'],'108']],
  rust_pointer_table: [[['1','100'],'111'],[['0','0'],'11']],
  rust_pointer_copy: [[['1','100'],'101'],[['0','100'],'100']],
  clang_dispatch: [[['2','10','3'],'31'],[['1','10','3'],'29']],
  clang_dispatch_twice: [[['3','10','3'],'14'],[['3','10','3'],'14']],
  clang_copied_dispatch: [[['1','10','3'],'29']],
  clang_ctor_callback: [[['10','3'],'31']],
  clang_constructors: [[['5'],'27'],[['0'],'22']],
  rust_dispatch: [[['2','10','3'],'31'],[['1','10','3'],'29']],
  rust_dispatch_twice: [[['3','10','3'],'14'],[['3','10','3'],'14']],
  rust_copied_dispatch: [[['1','10','3'],'29']],
  rust_ctor_callback: [[['10','3'],'31']],
  alias_table: [[['1','50'],'37'],[['0','50'],'63']],
  rust_aliases: [[['1','4294967295'],'6'],[['0','35'],'42']],
  rust_merged_aliases: [[['0','35'],'42'],[['1','4294967295'],'6']],
  rust_alias_entry: [[['35'],'42'],[['4294967295'],'6']],
  clang_triple: [[['10','3'],['13','9','7']],[['0','1'],['1','1','18446744073709551615']]],
  clang_triple_callback: [[['1','10','3'],['13','9','18446744073709551609']],[['0','10','3'],['13','9','7']]],
  clang_triple_calls: [[['10','3'],'26']],
  clang_byval: [[['13','9','7'],'26'],[['0','0','0'],'7']],
  clang_byval_calls: [[['10','3'],'26']],
  rust_triple: [[['10','3'],octets([13n,9n,7n])],[['0','1'],octets([1n,1n,(1n<<64n)-1n])]],
  rust_triple_calls: [[['10','3'],'26']],
  rust_triple_callback: [[['1','10','3'],octets([13n,9n,(1n<<64n)-7n])],[['0','10','3'],octets([13n,9n,7n])]],
};
for (const [name, inputs] of Object.entries(cases)) {
  test(name + ': LLVM font computes with browser HarfBuzz', async () => {
    const bytes = await readFile(new URL(name+'.ttf',assets));
    const manifest = JSON.parse(await readFile(new URL(name+'.json',assets)));
    const font = await RegisterFont.create(hb,bytes,manifest);
    for (const [args,expected] of inputs) {
      const results = font.invoke(args).results;
      if (Array.isArray(expected)) assert.deepEqual(results.map(value => value.unsigned),expected);
      else assert.equal(results[0].unsigned,expected);
    }
    assert.throws(() => font.invoke(inputs[0][0],false), {name:'IncompleteShaping'});
    if (name==='loop') {
      assert.throws(() => font.invoke(['15']), {name:'ExecutionBoundExceeded',message:'block_steps'});
    }
  });
}
