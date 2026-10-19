// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const path = require('node:path');
const {notaktoText, notaktoSignal, createNotaktoPlayground} = require('./controls.js');
const encode = s => '\ue000'+Array.from(s,c => String.fromCharCode(0xe100+c.charCodeAt(0))).join('')+'\ue001';
assert.equal(notaktoText('bA2\n\t\rB9'), encode('bA2   B9'));
assert.equal(notaktoText('é🙂\ue000\0\ud800'), encode('\x7f'.repeat(5)));
for (let code=1; code<=6; code++) assert.equal(notaktoSignal(1800+code), code);
for (const width of [0, 1800, 1807, 1801.4, NaN]) assert.equal(notaktoSignal(width),0);
const font = path.join(__dirname,'notakto-font.ttf');
function harness({missing=false, incompatible=false, rejected=false}={}) {
  function element() {
    return {value:'', textContent:'', dataset:{}, listeners:{}, attributes:{},
      append() {}, setAttribute(k,v) {this.attributes[k]=v;},
      addEventListener(k,v) {this.listeners[k]=v;},
      getBoundingClientRect() {
        if (incompatible) return {width:0};
        const glyphs=JSON.parse(execFileSync('hb-shape',[font,'--text='+this.textContent,'--output-format=json'], {encoding:'utf8',timeout:10000}));
        return {width:glyphs.reduce((s,g)=>s+g.ax,0)};
      },
    };
  }
  const e=Object.fromEntries(['record','drawing','status','reset','undo'].map(id=>[id,element()]));
  e.record.value='b';
  const buttons=['A1','A2','A4','B9'].map(move=>Object.assign(element(),{dataset:{move}}));
  global.document={body:{append(){}}, createElement:element, querySelector:s=>e[s.slice(1)],
    querySelectorAll:()=>buttons, fonts:{load:async()=>{
      if (rejected) throw new Error('Load failed');
      return missing?[]:[{}];
    }}};
  return {session:createNotaktoPlayground(),e,buttons,setIncompatible(v){incompatible=v;}};
}
(async()=>{
  const h=harness(),{session,e,buttons}=h;
  await session.ready;
  assert.equal(e.status.dataset.signal,'1');
  buttons[0].onclick();
  assert.equal(e.record.value,'b','Illegal moves must not change history');
  assert.match(e.status.textContent,/Choose an empty/);
  buttons[1].onclick();
  assert.equal(e.record.value,'bA2');
  assert.equal(e.status.dataset.signal,'1');
  buttons[2].onclick();
  assert.equal(e.record.value,'bA2','Closed boards reject moves');
  e.undo.onclick();
  assert.equal(e.record.value,'b');
  e.undo.onclick();
  assert.equal(e.record.value,'b');
  session.replace('bA1');
  assert.equal(e.status.dataset.signal,'4');
  buttons[3].onclick();
  assert.equal(e.record.value,'bA1','Invalid histories cannot accept button moves');
  e.reset.onclick();
  assert.equal(e.status.dataset.signal,'1');
  e.record.value='bB9';e.record.listeners.input();
  assert.equal(e.status.dataset.signal,'0');
  assert.equal(e.drawing.textContent,'');
  session.render();
  assert.equal(e.status.dataset.signal,'1');
  e.undo.onclick();
  assert.equal(e.record.value,'b');
  session.replace('b'.padEnd(256,' '));
  assert.equal(e.status.dataset.signal,'1');
  session.replace('b'.padEnd(257,' '));
  assert.equal(e.status.dataset.signal,'0');
  assert.equal(e.drawing.textContent,'');
  e.reset.onclick();
  h.setIncompatible(true);session.render();
  assert.equal(e.status.dataset.signal,'0');
  assert.equal(e.drawing.textContent,'');
  for (const options of [{missing:true},{incompatible:true},{rejected:true}]) {
    const broken=harness(options);await broken.session.ready;
    assert.match(broken.e.status.textContent,/Could not load or shape/);
    assert.equal(broken.e.status.dataset.signal,'0');
  }
  console.log('Notakto transport and controller integration checks passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
