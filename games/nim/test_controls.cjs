// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
const assert=require('node:assert/strict');
const path=require('node:path');
const {controllerHarness}=require('../shared/controller-harness.cjs');
const {createNimPlayground,nimText,nimSignal}=require('./controls.js');
const encode=s=>'\ue000'+Array.from(s,c=>String.fromCharCode(0xe100+c.charCodeAt(0))).join('')+'\ue001';
assert.equal(nimText('bN03,05,07;\n\t\r'),encode('bN03,05,07;   '));
assert.equal(nimText('🙂\ue000\0é\ud800'),encode('\x7f'.repeat(5)));
for(let n=1;n<=6;n++)assert.equal(nimSignal(1800+n),n);
for(const width of [0,1800,1807,1801.4,NaN])assert.equal(nimSignal(width),0);
const config={font:path.join(__dirname,'nim-font.ttf'),create:createNimPlayground,
  values:{record:'bN03,05,07;',startA:'3',startB:'5',startC:'7',rule:'N',first:'b',heap:'A',amount:'1'}};
(async()=>{
  const h=controllerHarness(config),{session,e}=h;await session.ready;
  assert.equal(e.status.dataset.signal,'1');
  e.amount.value='3';e.play.onclick();assert.equal(e.record.value,'bN03,05,07;');assert.match(e.status.textContent,/Take rejected/);
  e.amount.value='1';e.play.onclick();assert.equal(e.record.value,'bN03,05,07;A01;');
  e.undo.onclick();assert.equal(e.record.value,'bN03,05,07;');
  e.first.value='h';e.startA.value='1';e.startB.value='0';e.startC.value='0';e.reset.onclick();
  assert.equal(e.record.value,'hN01,00,00;');e.play.onclick();assert.equal(e.status.dataset.signal,'3');
  assert.equal(e.play.disabled,true);
  e.rule.value='M';e.reset.onclick();e.play.onclick();assert.equal(e.status.dataset.signal,'2');
  e.first.value='b';e.reset.onclick();assert.equal(e.status.dataset.signal,'3');
  e.rule.value='N';e.reset.onclick();assert.equal(e.status.dataset.signal,'2');
  e.rule.value='M';e.startA.value='2';e.startB.value='1';e.startC.value='1';e.reset.onclick();
  e.play.onclick();assert.equal(e.status.dataset.signal,'1');
  e.heap.value='C';e.play.onclick();assert.equal(e.status.dataset.signal,'2');
  e.undo.onclick();assert.equal(e.status.dataset.signal,'1');
  e.startA.value='';e.reset.onclick();assert.equal(e.status.dataset.signal,'5');
  e.startA.value='2';e.reset.onclick();e.amount.value='';e.play.onclick();
  assert.equal(e.record.value,'bM02,01,01;');assert.match(e.status.textContent,/Take rejected/);
  session.replace('hN01,00,00;A02;');assert.equal(e.status.dataset.signal,'4');
  session.replace('bad');assert.equal(e.status.dataset.signal,'5');
  e.record.value='bN03,05,07;';e.record.listeners.input();
  assert.equal(e.status.dataset.signal,'0');assert.equal(e.drawing.textContent,'');assert.equal(e.play.disabled,true);
  session.render();assert.equal(e.status.dataset.signal,'1');
  session.replace('bN03,05,07;'.padEnd(1024,' '));assert.equal(e.status.dataset.signal,'1');
  session.replace('bN03,05,07;'.padEnd(1025,' '));assert.equal(e.status.dataset.signal,'0');assert.equal(e.drawing.textContent,'');
  e.reset.onclick();h.setIncompatible(true);session.render();
  assert.equal(e.status.dataset.signal,'0');assert.equal(e.drawing.textContent,'');
  for(const options of [{missing:true},{incompatible:true},{rejected:true}]){
    const broken=controllerHarness({...config,...options});await broken.session.ready;
    assert.equal(broken.e.status.dataset.signal,'0');assert.match(broken.e.status.textContent,/Could not load or shape/);
  }
  console.log('Nim transport and controller integration checks passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
