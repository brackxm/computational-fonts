// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
const path=require('node:path');
const {checkController}=require('../shared/exact-controls-tests.cjs');
const {createDodgemPlayground}=require('./controls.js');
checkController({name:'Dodgem',font:path.join(__dirname,'dodgem-font.ttf'),create:createDodgemPlayground,
  values:{record:'h',setup:'h',from:'A3',to:'B3'},suffix:'A3B3;',afterMove:'hA3B3;',
  invalid:'hA1A2;',malformed:'hA3B3',
  endings:[['hA3B3;B3C3;C3C2;A2A3;A3A2;A2B2;C2X;B2B1;B1C1;C1X;',3],
           ['bB1B2;C1B1;B1A1;B2B3;A1B1;B1C1;C1C2;B3A3;A3B3;',2]],
}).catch(error=>{console.error(error);process.exitCode=1;});
