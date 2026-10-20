// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
const path=require('node:path');
const {checkController}=require('../shared/exact-controls-tests.cjs');
const {createKaylesPlayground}=require('./controls.js');
checkController({name:'Kayles',font:path.join(__dirname,'kayles-font.ttf'),create:createKaylesPlayground,
  values:{record:'h',setup:'h',pin:'01',kind:'S'},suffix:'01S;',afterMove:'h01S;',
  invalid:'h12D;',malformed:'h01S',
  endings:[['h06D;09S;03S;11S;08S;12S;',3],['b02S;01S;04S;05S;10S;',2]],
}).catch(error=>{console.error(error);process.exitCode=1;});
