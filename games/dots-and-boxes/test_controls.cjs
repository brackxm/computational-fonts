// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
const path=require('node:path');
const {checkController}=require('../shared/exact-controls-tests.cjs');
const {createDotsAndBoxesPlayground}=require('./controls.js');
checkController({name:'Dots and Boxes',font:path.join(__dirname,'dots-and-boxes-font.ttf'),create:createDotsAndBoxesPlayground,
  values:{record:'h',setup:'h',column:'A',row:'1',direction:'H'},suffix:'A1H;',afterMove:'hA1H;',
  resetValues:{column:'A',row:'1',direction:'V'},
  afterResetMove:'bA1V;',
  invalid:'hC3H;',malformed:'hA1H',
  endings:[['hA1H;B1H;A2H;B2V;B3H;C1V;C2V;',3],
           ['hA1H;B1H;A2H;B2H;C2V;',2],['hA1H;B1H;A2H;B3H;C1V;C2V;',7]],
}).catch(error=>{console.error(error);process.exitCode=1;});
