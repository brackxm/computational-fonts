// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
const assert=require('node:assert/strict');
const path=require('node:path');
const {controllerHarness}=require('../shared/controller-harness.cjs');
const {createTicTacToePlayground,ticTacToeText,ticTacToeSignal}=require('./controls.js');
const encode=s=>'\ue000'+Array.from(s,c=>String.fromCharCode(0xe100+c.charCodeAt(0))).join('')+'\ue001';
assert.equal(ticTacToeText('h1\n\t\r9'),encode('h1   9'));
assert.equal(ticTacToeText('🙂\ue000\0é\ud800'),encode('\x7f'.repeat(5)));
for(let n=1;n<=7;n++)assert.equal(ticTacToeSignal(1800+n),n);
for(const width of [0,1800,1808,1801.4,NaN])assert.equal(ticTacToeSignal(width),0);
const config={font:path.join(__dirname,'tic-tac-toe-font.ttf'),create:createTicTacToePlayground,
  values:{record:'h',setup:'h',square:'1'},moves:Array.from('123456789')};
(async()=>{
  const h=controllerHarness(config),{session,e,buttons}=h;await session.ready;
  assert.equal(e.status.dataset.signal,'1');
  buttons[0].onclick();assert.equal(e.record.value,'h1');
  buttons[0].onclick();assert.equal(e.record.value,'h1');assert.match(e.status.textContent,/Move rejected/);
  e.undo.onclick();assert.equal(e.record.value,'h');
  for(const square of '12768')buttons[Number(square)-1].onclick();
  assert.equal(e.record.value,'h12768');assert.equal(e.status.dataset.signal,'7');
  assert.equal(buttons[0].disabled,true);buttons[0].onclick();assert.equal(e.record.value,'h12768');
  e.undo.onclick();assert.equal(e.status.dataset.signal,'1');
  e.setup.value='b';e.reset.onclick();assert.equal(e.record.value,'b');
  e.square.value='5';e.play.onclick();assert.equal(e.record.value,'b');
  for(const square of '1762'){e.square.value=square;e.play.onclick();}
  assert.equal(e.record.value,'b1762');assert.equal(e.status.dataset.signal,'7');
  e.reset.onclick();buttons[0].onclick();buttons[1].onclick();assert.equal(e.status.dataset.signal,'2');
  session.replace('h11');assert.equal(e.status.dataset.signal,'4');
  session.replace('h0');assert.equal(e.status.dataset.signal,'5');
  e.record.value='h';e.record.listeners.input();
  assert.equal(e.status.dataset.signal,'0');assert.equal(e.drawing.textContent,'');assert.equal(buttons[0].disabled,true);
  session.render();assert.equal(e.status.dataset.signal,'1');
  session.replace('h'.padEnd(512,' '));assert.equal(e.status.dataset.signal,'1');
  session.replace('h'.padEnd(513,' '));assert.equal(e.status.dataset.signal,'0');assert.equal(e.drawing.textContent,'');
  e.reset.onclick();h.setIncompatible(true);session.render();
  assert.equal(e.status.dataset.signal,'0');assert.equal(e.drawing.textContent,'');
  for(const options of [{missing:true},{incompatible:true},{rejected:true}]){
    const broken=controllerHarness({...config,...options});await broken.session.ready;
    assert.equal(broken.e.status.dataset.signal,'0');assert.match(broken.e.status.textContent,/Could not load or shape/);
  }
  console.log('Tic-tac-toe transport and controller integration checks passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
