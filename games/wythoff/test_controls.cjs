// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
const assert=require('node:assert/strict');
const path=require('node:path');
const {controllerHarness}=require('../shared/controller-harness.cjs');
const {createWythoffPlayground,wythoffText,wythoffSignal}=require('./controls.js');
const encode=s=>'\ue000'+Array.from(s,c=>String.fromCharCode(0xe100+c.charCodeAt(0))).join('')+'\ue001';
assert.equal(wythoffText('b31,47;\n\t\rA01;'),encode('b31,47;   A01;'));
assert.equal(wythoffText('🙂\ue000\ud800\0é'),encode('\x7f'.repeat(5)));
for(let n=1;n<=6;n++)assert.equal(wythoffSignal(1800+n),n);
for(const width of [0,1800,1807,1801.4,NaN])assert.equal(wythoffSignal(width),0);
const config={font:path.join(__dirname,'wythoff-font.ttf'),create:createWythoffPlayground,
  values:{record:'b31,47;',startA:'31',startB:'47',first:'b',heap:'A',amount:'1'}};
(async()=>{
  const h=controllerHarness(config),{session,e}=h;
  await session.ready;
  assert.equal(e.status.dataset.signal,'1');
  assert.equal(e.play.disabled,false);
  e.amount.value='30';e.play.onclick();
  assert.equal(e.record.value,'b31,47;');
  assert.match(e.status.textContent,/Move rejected/);
  e.amount.value='1';e.play.onclick();
  assert.equal(e.record.value,'b31,47;A01;');
  assert.equal(e.status.dataset.signal,'1');
  e.undo.onclick();assert.equal(e.record.value,'b31,47;');
  e.first.value='h';e.startA.value='1';e.startB.value='2';e.reset.onclick();
  assert.equal(e.record.value,'h01,02;');
  e.play.onclick();assert.equal(e.status.dataset.signal,'2');
  assert.equal(e.play.disabled,true);
  e.play.onclick();assert.equal(e.record.value,'h01,02;A01;');
  e.undo.onclick();assert.equal(e.record.value,'h01,02;');
  e.startB.value='1';e.reset.onclick();e.heap.value='D';e.play.onclick();
  assert.equal(e.status.dataset.signal,'3');
  assert.match(e.status.textContent,/You win/);
  e.startA.value='';e.reset.onclick();
  assert.equal(e.status.dataset.signal,'5','Empty setup must not become a zero heap');
  e.startA.value='1';e.startB.value='2';e.reset.onclick();
  e.amount.value='';e.play.onclick();
  assert.equal(e.record.value,'h01,02;','Empty amount must not append a move');
  assert.match(e.status.textContent,/Move rejected/);
  session.replace('h01,02;A02;');assert.equal(e.status.dataset.signal,'4');
  e.play.onclick();assert.equal(e.record.value,'h01,02;A02;');
  session.replace('bad');assert.equal(e.status.dataset.signal,'5');
  e.record.value='b31,47;';e.record.listeners.input();
  assert.equal(e.status.dataset.signal,'0');assert.equal(e.drawing.textContent,'');
  assert.equal(e.play.disabled,true);
  session.render();assert.equal(e.status.dataset.signal,'1');
  session.replace('b31,47;'.padEnd(1024,' '));assert.equal(e.status.dataset.signal,'1');
  session.replace('b31,47;'.padEnd(1025,' '));
  assert.equal(e.status.dataset.signal,'0');assert.equal(e.drawing.textContent,'');
  e.reset.onclick();h.setIncompatible(true);session.render();
  assert.equal(e.status.dataset.signal,'0');assert.equal(e.drawing.textContent,'');
  for(const options of [{missing:true},{incompatible:true},{rejected:true}]){
    const broken=controllerHarness({...config,...options});await broken.session.ready;
    assert.equal(broken.e.status.dataset.signal,'0');assert.match(broken.e.status.textContent,/Could not load or shape/);
    assert.equal(broken.e.play.disabled,true);
  }
  console.log('Wythoff transport and controller integration checks passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
