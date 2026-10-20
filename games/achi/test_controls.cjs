// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
const path=require('node:path');
const {checkController}=require('../shared/exact-controls-tests.cjs');
const {createAchiPlayground}=require('./controls.js');
checkController({name:'Achi',font:path.join(__dirname,'achi-font.ttf'),create:createAchiPlayground,
  values:{record:'h',setup:'h',action:'place',from:'A1',to:'A1'},suffix:'A1;',afterMove:'hA1;',
  resetValues:{action:'place',to:'A1'},
  moves:['='],invalid:'hA1A2;',malformed:'hA1',
  endings:[['hB2;B3;C1;B2C2;B3C3;',3],['bA1;B1;A3;A1A2;',2],['hA1;=',7]],
}).catch(error=>{console.error(error);process.exitCode=1;});
