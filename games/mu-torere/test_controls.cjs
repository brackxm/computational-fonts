// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
const assert=require('node:assert/strict');
const path=require('node:path');
const {controllerHarness}=require('../shared/controller-harness.cjs');
const {createMuTorerePlayground,muTorereText,muTorereSignal}=require('./controls.js');
const encode=s=>'\ue000'+Array.from(s,c=>String.fromCharCode(0xe100+c.charCodeAt(0))).join('')+'\ue001';
assert.equal(muTorereText('h1\n\t\r9='),encode('h1   9='));
assert.equal(muTorereText('🙂\ue000\0é\ud800'),encode('\x7f'.repeat(5)));
for(let n=1;n<=7;n++)assert.equal(muTorereSignal(1800+n),n);
for(const width of [0,1800,1808,1801.4,NaN])assert.equal(muTorereSignal(width),0);
const config={font:path.join(__dirname,'mu-torere-font.ttf'),create:createMuTorerePlayground,
  values:{record:'h',setup:'h',point:'1'},moves:['1','2','9','=','8','7']};
(async()=>{
  const h=controllerHarness(config),{session,e,buttons}=h;await session.ready;
  assert.equal(e.status.dataset.signal,'1');
  buttons[1].onclick();assert.equal(e.record.value,'h');assert.match(e.status.textContent,/Move rejected/);
  e.play.onclick();assert.equal(e.record.value,'h1');e.undo.onclick();assert.equal(e.record.value,'h');
  buttons[0].onclick();assert.equal(e.record.value,'h1');assert.equal(e.status.dataset.signal,'1');
  e.undo.onclick();assert.equal(e.record.value,'h');
  buttons[3].onclick();assert.equal(e.record.value,'h=');assert.equal(e.status.dataset.signal,'7');
  assert.equal(buttons[0].disabled,true);buttons[0].onclick();assert.equal(e.record.value,'h=');
  e.setup.value='w';e.reset.onclick();assert.equal(e.record.value,'w');
  buttons[4].onclick();buttons[0].onclick();buttons[5].onclick();
  assert.equal(e.record.value,'w817');assert.equal(e.status.dataset.signal,'3');
  e.setup.value='l';e.reset.onclick();buttons[3].onclick();
  assert.equal(e.record.value,'l','A forced-win font must decline a draw offer');
  buttons[2].onclick();buttons[0].onclick();assert.equal(e.status.dataset.signal,'2');
  e.undo.onclick();assert.equal(e.status.dataset.signal,'1');
  session.replace('bad');assert.equal(e.status.dataset.signal,'5');
  e.record.value='h';e.record.listeners.input();
  assert.equal(e.status.dataset.signal,'0');assert.equal(e.drawing.textContent,'');assert.equal(buttons[0].disabled,true);
  session.render();assert.equal(e.status.dataset.signal,'1');
  session.replace('h'.padEnd(4096,' '));assert.equal(e.status.dataset.signal,'1');
  session.replace('h'.padEnd(4097,' '));assert.equal(e.status.dataset.signal,'0');assert.equal(e.drawing.textContent,'');
  e.reset.onclick();h.setIncompatible(true);session.render();
  assert.equal(e.status.dataset.signal,'0');assert.equal(e.drawing.textContent,'');
  for(const options of [{missing:true},{incompatible:true},{rejected:true}]){
    const broken=controllerHarness({...config,...options});await broken.session.ready;
    assert.equal(broken.e.status.dataset.signal,'0');assert.match(broken.e.status.textContent,/Could not load or shape/);
  }
  console.log('Mū tōrere transport and controller integration checks passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
