// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
const assert=require('node:assert/strict');
const {controllerHarness}=require('./controller-harness.cjs');
const {gameText,gameSignal}=require('./game-controls.js');

async function checkController(config){
  assert.equal(gameText('🙂\ue000\0é\ud800'),'\ue000'+'\ue17f'.repeat(5)+'\ue001');
  for(let n=1;n<=6;n++)assert.equal(gameSignal(1800+n),n);
  for(const width of [0,1800,1808,1801.4,NaN])assert.equal(gameSignal(width),0);
  const h=controllerHarness(config),{session,e}=h;
  await session.ready;
  assert.equal(e.status.dataset.signal,'1');
  e.play.onclick();assert.equal(e.record.value,config.afterMove);
  e.undo.onclick();assert.equal(e.record.value,'h');
  session.replace(config.invalid);assert.equal(e.status.dataset.signal,'4');
  session.replace(config.malformed);assert.equal(e.status.dataset.signal,'5');
  for(const [source,code] of config.endings){
    session.replace(source);assert.equal(e.status.dataset.signal,String(code));
    assert.equal(e.play.disabled,true);
    session.propose(config.suffix);assert.equal(e.record.value,source);
    session.replace(source+'?🙂');assert.equal(e.status.dataset.signal,String(code));
  }
  e.setup.value='b';e.reset.onclick();assert.equal(e.record.value,'b');
  assert.equal(e.status.dataset.signal,'1');
  for(const [id,value] of Object.entries(config.resetValues||{}))assert.equal(e[id].value,value);
  if(config.afterResetMove){e.play.onclick();assert.equal(e.record.value,config.afterResetMove);}
  e.record.value='h';e.record.listeners.input();
  assert.equal(e.status.dataset.signal,'0');assert.equal(e.drawing.textContent,'');
  assert.equal(e.play.disabled,true);
  session.render();assert.equal(e.status.dataset.signal,'1');
  session.replace('h'.padEnd(1025,' '));
  assert.equal(e.status.dataset.signal,'0');assert.equal(e.drawing.textContent,'');
  session.replace('h');h.setIncompatible(true);session.render();
  assert.equal(e.status.dataset.signal,'0');assert.equal(e.drawing.textContent,'');
  for(const options of [{missing:true},{incompatible:true},{rejected:true}]){
    const broken=controllerHarness({...config,...options});await broken.session.ready;
    assert.equal(broken.e.status.dataset.signal,'0');
    assert.match(broken.e.status.textContent,/Could not load or shape/);
  }
  console.log(config.name+' transport and controller checks passed.');
}
module.exports={checkController};
