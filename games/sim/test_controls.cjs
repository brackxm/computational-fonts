// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
const path=require('node:path');
const {checkController}=require('../shared/exact-controls-tests.cjs');
const {createSimPlayground}=require('./controls.js');
checkController({name:'Sim',font:path.join(__dirname,'sim-font.ttf'),create:createSimPlayground,
  values:{record:'h',setup:'h',edge:'AB'},suffix:'AB;',afterMove:'hAB;',
  invalid:'hAB;AB;',malformed:'hAB',resetValues:{edge:'AC'},afterResetMove:'bAC;',
  endings:[['hEF;DF;DE;',2],['bEF;DF;CE;AF;',3],['bEF;DF;DE;',2]],
}).catch(error=>{console.error(error);process.exitCode=1;});
