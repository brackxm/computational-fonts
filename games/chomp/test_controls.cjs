// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
const path=require('node:path');
const {checkController}=require('../shared/exact-controls-tests.cjs');
const {createChompPlayground}=require('./controls.js');
checkController({name:'Chomp',font:path.join(__dirname,'chomp-font.ttf'),create:createChompPlayground,
  values:{record:'h',setup:'h',column:'C',row:'3'},suffix:'C3;',afterMove:'hC3;',
  invalid:'hA1;',malformed:'hC3',
  endings:[['hD3;E2;C3;F1;E1;D1;C1;B1;',3],['bC5;A4;A3;D2;C2;B2;A2;',2]],
}).catch(error=>{console.error(error);process.exitCode=1;});
