// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
const path=require('node:path');
const {checkController}=require('../shared/exact-controls-tests.cjs');
const {createDomineeringPlayground}=require('./controls.js');
checkController({name:'Domineering',font:path.join(__dirname,'domineering-font.ttf'),create:createDomineeringPlayground,
  values:{record:'h',setup:'h',column:'A',row:'2',direction:'V'},suffix:'A2V;',afterMove:'hA2V;',
  resetValues:{column:'A',row:'1',direction:'H'},
  invalid:'hA1H;',malformed:'hA1V',
  endings:[['hA2V;B3V;C3V;D2V;',3],['bA1H;B2H;C1H;',2]],
}).catch(error=>{console.error(error);process.exitCode=1;});
