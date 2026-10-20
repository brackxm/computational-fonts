// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
// Controller tests measure the real font with HarfBuzz; fake DOM is presentation.
const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const path = require('node:path');
const {connectFourText, connectFourSignal, createConnectFourPlayground} = require('./controls.js');
const font = path.join(__dirname,'connect-four-font.ttf');
function shapeWidth(text, disabled=false) {
  const args=[font,'--text='+text,'--output-format=json'];
  if(disabled) args.push('--features=liga=0');
  return JSON.parse(execFileSync('hb-shape',args,{encoding:'utf8'})).reduce((a,g)=>a+g.ax,0);
}
const cases={b:1,b1:1,b135:2,b1351:5,bb:4,b0:4,'b4444':3};
for(const [source,status] of Object.entries(cases)) {
  assert.equal(connectFourSignal(shapeWidth(connectFourText(source))),status,source);
  assert.equal(connectFourSignal(shapeWidth(connectFourText(source),true)),0);
}
for (const source of ['bλ','b🙂','b\ue162','b\n']) assert.equal(connectFourSignal(shapeWidth(connectFourText(source))),4);
for (const width of [0,1000,1010,1001.3,999]) assert.equal(connectFourSignal(width),0);
class Element {
  constructor(){this.value='';this.textContent='';this.dataset={};this.style={};this.listeners={};this.disabled=false;}
  setAttribute(n,v){this[n]=v;}
  addEventListener(n,f){this.listeners[n]=f;}
  append(){}
  getBoundingClientRect(){return {width:this.className==='probe'?shapeWidth(this.textContent):500};}
}
async function test({disabled=false,missing=false,rejected=false,unavailable=false,throws=false}={}) {
  const nodes=Object.fromEntries(['history','drawing','status','undo','reset','board-area'].map(id=>[id,new Element()]));
  nodes.history.value='b';
  const buttons=Array.from({length:7},(_,i)=>{const e=new Element();e.dataset.column=String(i+1);return e;});
  const listeners={};
  global.document={getElementById:id=>nodes[id],querySelectorAll:()=>buttons,body:new Element(),
    createElement:()=>{const e=new Element();if(disabled)e.getBoundingClientRect=()=>({width:0});return e;},
    addEventListener:(n,f)=>listeners[n]=f,
    fonts:unavailable ? undefined : {load:()=>{
      if(throws) throw new Error('font loader threw');
      return rejected?Promise.reject(new Error('font unavailable')):Promise.resolve(missing?[]:[{}]);
    }}};
  const app=createConnectFourPlayground();await app.ready;
  if(disabled||missing||rejected||unavailable||throws){assert.equal(nodes.drawing.textContent,'');assert.ok(buttons.every(b=>b.disabled));return;}
  assert.equal(nodes.status.dataset.signal,'1');assert.equal(nodes.undo.disabled,true);
  buttons[0].onclick();assert.equal(nodes.history.value,'b1');
  let prevented=false;
  listeners.keydown({target:buttons[0],key:'3',preventDefault(){prevented=true;}});
  assert.equal(prevented,true);assert.equal(nodes.history.value,'b13');
  buttons[4].onclick();assert.equal(nodes.history.value,'b135');assert.equal(nodes.status.dataset.signal,'2');
  assert.ok(buttons.every(b=>b.disabled));buttons[0].onclick();assert.equal(nodes.history.value,'b135');
  nodes.undo.onclick();assert.equal(nodes.history.value,'b13');assert.equal(nodes.status.dataset.signal,'1');
  nodes.reset.onclick();assert.equal(nodes.history.value,'b');
  app.replace('b4444');assert.equal(nodes.status.dataset.signal,'3');nodes.undo.onclick();assert.equal(nodes.status.dataset.signal,'1');
  app.replace('b1351');assert.equal(nodes.status.dataset.signal,'5');
  app.replace('bλ');assert.equal(nodes.status.dataset.signal,'4');
  app.replace('b🙂');nodes.undo.onclick();assert.equal(nodes.history.value,'b');assert.equal(nodes.status.dataset.signal,'1');
  nodes.history.value='b1';nodes.history.listeners.input();assert.equal(nodes.drawing.textContent,'');assert.ok(buttons.every(b=>b.disabled));app.render();
  assert.equal(nodes.status.dataset.signal,'1');
  listeners.keydown({target:nodes.history,key:'2',preventDefault(){throw new Error('editor key intercepted');}});
  assert.equal(nodes.history.value,'b1');
  app.replace('');assert.equal(nodes.drawing.textContent,'');
  app.replace('b'+'1'.repeat(256));assert.equal(nodes.drawing.textContent,'');
  app.replace('b65342431477741666255');assert.equal(nodes.status.dataset.signal,'2');
}
(async()=>{await test();await test({disabled:true});await test({missing:true});await test({rejected:true});await test({unavailable:true});await test({throws:true});console.log('Controller tests passed (real HarfBuzz font signals).');})().catch(e=>{console.error(e);process.exitCode=1;});
