// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
const assert = require('node:assert/strict');
const { validate, EXAMPLES } = require('./smiles-controls.js');
for (const source of Object.values(EXAMPLES)) assert.equal(validate(source).input, `{${source}}`);
for (const source of ['C', 'CCCCCCCCCC', 'C(C)(N)O', 'C(=O)O', 'C1CCC=1', 'C12CC1CC2', 'C1CC1C1CC1', 'BPNOSFIH', 'c1ccccc1', 'c1ccncc1', 'c1ccoc1', 'c1ccsc1', 'b1ccccc1', 'p1ccccc1', 'Cc1ccccc1', 'Clc1ccccc1', 'c1cc-ccc1', '[nH]1cccc1', '[NH4+]', '[O-]', 'CC(=O)[O-]', '[CH3][NH3+]', '[N++]', '[N+2]', '[Cl-]', '[NH0-3]', '[NH4+].[Cl-]', 'C.C', 'CCO.C1CC1', 'C1CC1.C1CC1']) {
  assert.ok(validate(source).atoms <= 10, source);
}
for (const source of ['', 'CC O', 'C\nO', '{CCO}', '[Na+]', '.', '.C', 'C.', 'C..O', 'C=.O', 'C(.O)', 'C.(O)', 'C1.C1', 'C(C.O)', 'C1CC1.C1CC', 'C@C', 'C=(', 'C()',
  '(C)', 'C)', 'C(C', 'C=', '=C', 'C==O', 'C1CC', 'C11', 'C1C1', 'C=1CCC1', 'CCCCCCCCCCC',
  'C(C(C(C)))', 'C4CCC4', 'C(C1)1', 'C1(1C)', 'f1ccccc1', '[N2+]', '[N+4]', '[NH5]', '[N+-]', '[13C]', '[C@H]', '[C:1]', '[NH4', 'N+','[]', 'c1:ccccc1', 'c1ccccc1.', 'c1ccccc1ccccC']) {
  assert.throws(() => validate(source), undefined, source);
}
console.log('SMILES controls: examples, limits and malformed inputs passed.');

const fs = require('node:fs');
const path = require('node:path');
const manifestPath = path.join(__dirname, 'smiles-font.topologies.json');
if (fs.existsSync(manifestPath)) {
  const supported = new Set(JSON.parse(fs.readFileSync(manifestPath, 'utf8')).map(item => JSON.stringify(item)));
  for (const source of ['CCO.C1CC1','C1CC1.C1CC1','C1CC1.[NH4+]','[Cl-].C1CC1','[nH]1cccc1','c1cc[nH]c1','[nH+]1ccccc1','[CH]1CCCCC1','c1ccccc1','c2ccccc2','c1ccncc1','c1ccsc1','Cc1ccccc1','Clc1ccccc1','c1cc-ccc1','c1ccc2ccccc2c1','C1CCCCC1','C2=CC=CC=C2','O1CCNCC1','CC1CCCCC1','C1CC(C)CCC1','C12CC1CC2','C12(CCC1)CCC2']) {
    assert.ok(validate(source,supported));
  }
  assert.throws(() => validate('C1CC(C)(C)CCC1',supported), /outside/);
  assert.throws(() => validate('C1CC2CCC1C2',supported), /outside/);
  console.log('SMILES supported ring topology checks passed.');
}

for (const source of ['[nH]', '[NH4+]', '[O-]', '[CH3]', '[N+++]', '[N+3]', '[NH0-]']) assert.equal(validate(source).atoms, 1, source);
assert.equal(validate('[CH3][NH3+]').atoms, 2);

assert.equal(validate('[NH4+].[Cl-]').fragments, 2);
assert.equal(validate('[NH4+].[Cl-]').atoms, 2);
assert.equal(validate('C.C.C.C.C.C.C.C.C.C').atoms, 10);
assert.throws(() => validate('CCCCCC.CCCCC'), /10 atoms/);
assert.throws(() => validate('C.C.C.C.C.C.C.C.C.C.C'), /10 atoms/);
if (fs.existsSync(manifestPath)) {
  const supported = new Set(JSON.parse(fs.readFileSync(manifestPath, 'utf8')).map(item => JSON.stringify(item)));
  assert.throws(() => validate('CCO.C1CC(C)(C)CCC1',supported), /outside/);
}
console.log('Disconnected fragment counts, topology checks and boundary errors passed.');

for (const source of ['C(C(C))O','C(C(C))(C)','C(-C)(-C)(-C)C(-C)(-C)C(-C)(-C)','C1CCC1CBr']) {
  assert.ok(validate(source).atoms <= 10,source);
}
