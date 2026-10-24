// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
const assert=require('node:assert/strict');
const path=require('node:path');
const fs=require('node:fs');
const {controllerHarness}=require('../../shared/controller-harness.cjs');
const {createResearchPlayground,researchText}=require('./controls.js');
assert.equal(researchText('b'),'\ue000\ue162'+'\ue120'.repeat(512)+'\ue001');
const html=fs.readFileSync(path.join(__dirname,'playground.html'),'utf8');
for(const [id,wanted] of [['from','B5'],['to','C3']]){
  const select=html.match(new RegExp('<select id="'+id+'">([\\s\\S]*?)</select>'))[1];
  assert.equal((select.match(/<option selected>/g)||[]).length,1);
  assert.ok(select.includes('<option selected>'+wanted+'</option>'));
}
const config={font:path.join(__dirname,'gardner-research.ttf'),create:createResearchPlayground,
  values:{record:'b',from:'B5',to:'C3',promotion:''}};
(async()=>{
  const {session,e}=controllerHarness(config);await session.ready;
  assert.equal(e.status.dataset.signal,'1');
  e.play.onclick();assert.equal(e.record.value,'bB5C3;');assert.equal(e.status.dataset.signal,'1');
  e.undo.onclick();assert.equal(e.record.value,'b');
  e.from.value='B4';e.to.value='A3';e.play.onclick();
  assert.equal(e.record.value,'bB4A3;');assert.equal(e.status.dataset.signal,'6');
  assert.equal(e.play.disabled,true);assert.match(e.status.textContent,/Unproved opening/);
  e.undo.onclick();assert.equal(e.record.value,'b');assert.equal(e.status.dataset.signal,'1');
  session.replace('bB4B3;');assert.equal(e.status.dataset.signal,'6');
  e.reset.onclick();assert.equal(e.from.value,'B5');assert.equal(e.to.value,'C3');
  session.replace('b'.padEnd(513,' '));assert.equal(e.status.dataset.signal,'0');assert.equal(e.drawing.textContent,'');
  console.log('Research controller checks passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
