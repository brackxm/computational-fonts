// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
const assert=require('node:assert/strict');
const path=require('node:path');
const {controllerHarness}=require('../shared/controller-harness.cjs');
const {createGardnerPlayground,gardnerText}=require('./controls.js');
assert.equal(gardnerText('b\n\t'),'\ue000\ue162\ue120\ue120'+'\ue120'.repeat(256)+'\ue001');
assert.equal(gardnerText('🙂'),'\ue000\ue17f'+'\ue120'.repeat(128)+'\ue001');
const config={font:path.join(__dirname,'gardner-font.ttf'),create:createGardnerPlayground,
  values:{record:'b',from:'B4',to:'A3',promotion:''}};
(async()=>{
  const h=controllerHarness(config),{session,e}=h;await session.ready;
  assert.equal(e.status.dataset.signal,'1');
  e.play.onclick();assert.equal(e.record.value,'bB4A3;');
  e.play.onclick();assert.equal(e.record.value,'bB4A3;');assert.match(e.status.textContent,/Move rejected/);
  e.undo.onclick();assert.equal(e.record.value,'b');assert.equal(e.status.dataset.signal,'1');
  session.replace('bA1A1;');assert.equal(e.status.dataset.signal,'4');
  session.replace('bgarbage');assert.equal(e.status.dataset.signal,'5');
  e.reset.onclick();assert.equal(e.record.value,'b');assert.equal(e.from.value,'B4');assert.equal(e.to.value,'A3');
  e.record.value='bB4A3;';e.record.listeners.input();
  assert.equal(e.status.dataset.signal,'0');assert.equal(e.drawing.textContent,'');assert.equal(e.play.disabled,true);
  session.render();assert.equal(e.status.dataset.signal,'1');
  session.replace('b'.padEnd(2048,' '));assert.equal(e.status.dataset.signal,'1');
  session.replace('b'.padEnd(2049,' '));assert.equal(e.status.dataset.signal,'0');assert.equal(e.drawing.textContent,'');
  for(const options of [{missing:true},{incompatible:true},{rejected:true}]){
    const broken=controllerHarness({...config,...options});await broken.session.ready;
    assert.equal(broken.e.status.dataset.signal,'0');assert.match(broken.e.status.textContent,/Could not load or shape/);
  }
  console.log('Gardner controller integration checks passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
