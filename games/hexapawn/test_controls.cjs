// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
const assert=require('node:assert/strict');
const path=require('node:path');
const {controllerHarness}=require('../shared/controller-harness.cjs');
const {createHexapawnPlayground,hexapawnText,hexapawnSignal}=require('./controls.js');
const encode=s=>'\ue000'+Array.from(s,c=>String.fromCharCode(0xe100+c.charCodeAt(0))).join('')+'\ue001';
assert.equal(hexapawnText('hB1B2\n\t\r'),encode('hB1B2   '));
assert.equal(hexapawnText('🙂\ue000\0é\ud800'),encode('\x7f'.repeat(5)));
for(let n=1;n<=6;n++)assert.equal(hexapawnSignal(1800+n),n);
for(const width of [0,1800,1807,1801.4,NaN])assert.equal(hexapawnSignal(width),0);
const config={font:path.join(__dirname,'hexapawn-font.ttf'),create:createHexapawnPlayground,
  values:{record:'h',setup:'h',from:'B1',to:'B2'}};
(async()=>{
  const h=controllerHarness(config),{session,e}=h;await session.ready;
  assert.equal(e.status.dataset.signal,'1');
  e.play.onclick();assert.equal(e.record.value,'hB1B2');
  e.play.onclick();assert.equal(e.record.value,'hB1B2');assert.match(e.status.textContent,/Move rejected/);
  e.from.value='C1';e.play.onclick();assert.equal(e.record.value,'hB1B2C1B2');
  e.from.value='A1';e.to.value='A2';e.play.onclick();assert.equal(e.status.dataset.signal,'2');
  assert.equal(e.play.disabled,true);e.play.onclick();assert.equal(e.record.value,'hB1B2C1B2A1A2');
  e.undo.onclick();assert.equal(e.status.dataset.signal,'1');
  e.setup.value='b';e.reset.onclick();assert.equal(e.record.value,'b');
  assert.equal(e.from.value,'A3');assert.equal(e.to.value,'B2');
  e.play.onclick();e.from.value='C3';e.to.value='C2';e.play.onclick();
  e.from.value='C2';e.to.value='C1';e.play.onclick();assert.equal(e.status.dataset.signal,'3');
  e.undo.onclick();assert.equal(e.status.dataset.signal,'1');
  session.replace('hA1A3');assert.equal(e.status.dataset.signal,'4');
  session.replace('hA1');assert.equal(e.status.dataset.signal,'5');
  e.record.value='h';e.record.listeners.input();
  assert.equal(e.status.dataset.signal,'0');assert.equal(e.drawing.textContent,'');assert.equal(e.play.disabled,true);
  session.render();assert.equal(e.status.dataset.signal,'1');
  session.replace('h'.padEnd(512,' '));assert.equal(e.status.dataset.signal,'1');
  session.replace('h'.padEnd(513,' '));assert.equal(e.status.dataset.signal,'0');assert.equal(e.drawing.textContent,'');
  e.reset.onclick();h.setIncompatible(true);session.render();
  assert.equal(e.status.dataset.signal,'0');assert.equal(e.drawing.textContent,'');
  for(const options of [{missing:true},{incompatible:true},{rejected:true}]){
    const broken=controllerHarness({...config,...options});await broken.session.ready;
    assert.equal(broken.e.status.dataset.signal,'0');assert.match(broken.e.status.textContent,/Could not load or shape/);
  }
  console.log('Hexapawn transport and controller integration checks passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
