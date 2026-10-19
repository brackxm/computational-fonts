// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
const assert=require('node:assert/strict');
const path=require('node:path');
const {controllerHarness}=require('../shared/controller-harness.cjs');
const {createCramPlayground,cramText,cramSignal}=require('./controls.js');
const encode=s=>'\ue000'+Array.from(s,c=>String.fromCharCode(0xe100+c.charCodeAt(0))).join('')+'\ue001';
assert.equal(cramText('bA1H\n\t\r'),encode('bA1H   '));
assert.equal(cramText('🙂\ue000\0é\ud800'),encode('\x7f'.repeat(5)));
for(let n=1;n<=6;n++)assert.equal(cramSignal(1800+n),n);
for(const width of [0,1800,1807,1801.4,NaN])assert.equal(cramSignal(width),0);
const config={font:path.join(__dirname,'cram-font.ttf'),create:createCramPlayground,
  values:{record:'b',cell:'A1',direction:'H'}};
(async()=>{
  const h=controllerHarness(config),{session,e}=h;await session.ready;
  assert.equal(e.status.dataset.signal,'1');
  e.play.onclick();assert.equal(e.record.value,'bA1H');
  e.play.onclick();assert.equal(e.record.value,'bA1H');assert.match(e.status.textContent,/Placement rejected/);
  e.cell.value='E5';e.play.onclick();assert.equal(e.record.value,'bA1H','AI tiles also reject overlap');
  e.cell.value='F1';e.play.onclick();assert.equal(e.record.value,'bA1H','Out-of-board placements must not change history');
  e.direction.value='V';e.play.onclick();assert.equal(e.record.value,'bA1HF1V');
  e.undo.onclick();assert.equal(e.record.value,'bA1H');
  e.reset.onclick();assert.equal(e.record.value,'b');
  session.replace('bC3H');assert.equal(e.status.dataset.signal,'4');
  e.play.onclick();assert.equal(e.record.value,'bC3H');
  session.replace('bA1');assert.equal(e.status.dataset.signal,'5');
  const terminal='bE5HC5HD4HB4VA3V';
  session.replace(terminal);assert.equal(e.status.dataset.signal,'2');assert.equal(e.play.disabled,true);
  e.play.onclick();assert.equal(e.record.value,terminal);
  session.replace(terminal+'anything🙂');assert.equal(e.status.dataset.signal,'2');
  e.record.value='b';e.record.listeners.input();
  assert.equal(e.status.dataset.signal,'0');assert.equal(e.drawing.textContent,'');assert.equal(e.play.disabled,true);
  session.render();assert.equal(e.status.dataset.signal,'1');
  session.replace('b'.padEnd(256,' '));assert.equal(e.status.dataset.signal,'1');
  session.replace('b'.padEnd(257,' '));assert.equal(e.status.dataset.signal,'0');assert.equal(e.drawing.textContent,'');
  e.reset.onclick();h.setIncompatible(true);session.render();
  assert.equal(e.status.dataset.signal,'0');assert.equal(e.drawing.textContent,'');
  for(const options of [{missing:true},{incompatible:true},{rejected:true}]){
    const broken=controllerHarness({...config,...options});await broken.session.ready;
    assert.equal(broken.e.status.dataset.signal,'0');assert.match(broken.e.status.textContent,/Could not load or shape/);
  }
  console.log('Cram transport and controller integration checks passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
