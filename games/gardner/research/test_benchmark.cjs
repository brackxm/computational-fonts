// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
// Failure-injection checks for benchmark controls; real shaping is tested separately.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const html=fs.readFileSync(path.join(__dirname,'benchmark.html'),'utf8');
const script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const manifest=JSON.parse(fs.readFileSync(path.join(__dirname,'manifest.json')));
const fixture=JSON.parse(fs.readFileSync(path.join(__dirname,'inputs/replay.json')));
const elements=Object.fromEntries(['load','run','result','drawing','record','caption','raw','history'].map(id=>[id,{disabled:id==='run',textContent:'',value:''}]));
const fonts=new Set();
const statuses=new Map(fixture.positions.map(p=>[p.source,p.status]));
function measureText(encoded){
  const source=Array.from(encoded).slice(1,-1).map(c=>String.fromCharCode(c.codePointAt(0)-0xe100)).join('').trimEnd();
  assert.ok(statuses.has(source),'Unknown benchmark fixture');
  return {width:badWidth?1800:1800+statuses.get(source)};
}
let offline=true,wrongHash=false,badWidth=false,step=1,now=0;
const context={
  document:{getElementById:id=>elements[id],fonts,
    createElement:()=>({getContext:()=>({measureText})})},
  FontFace:class{async load(){return this}},
  fetch:async url=>{
    if(offline)throw Error('Network unavailable');
    return url.endsWith('.json')?{json:async()=>fixture}:{arrayBuffer:async()=>new ArrayBuffer(16)};
  },
  crypto:{subtle:{digest:async()=>Uint8Array.from(Buffer.from(wrongHash?'0'.repeat(64):manifest.font_sha256,'hex')).buffer}},
  performance:{now:()=>{now+=step;return now}},
  requestAnimationFrame:callback=>callback(0),
};
vm.runInNewContext(script,context,{filename:'benchmark.html'});
const history=()=>JSON.parse(elements.history.textContent);
const latest=()=>JSON.parse(elements.raw.textContent);
(async()=>{
  await elements.load.onclick();
  assert.equal(elements.load.disabled,false);
  assert.equal(elements.run.disabled,true);
  assert.equal(latest().phase,'load');assert.equal(latest().status,'fail');
  assert.match(latest().error,/Network unavailable/);

  offline=false;wrongHash=true;
  await elements.load.onclick();
  assert.match(latest().error,/Font hash mismatch/);
  assert.equal(fonts.size,0,'Failed font remained registered');
  assert.equal(elements.load.disabled,false);assert.equal(elements.run.disabled,true);
  assert.equal(history().length,2);

  wrongHash=false;
  await elements.load.onclick();
  assert.equal(elements.load.disabled,true);assert.equal(elements.run.disabled,false);
  assert.equal(fonts.size,1);
  badWidth=true;
  await elements.run.onclick();
  assert.match(latest().error,/Prefix mismatch/);
  assert.equal(latest().phase,'replay');assert.equal(elements.run.disabled,false);

  badWidth=false;step=300;
  await elements.run.onclick();
  assert.equal(latest().status,'fail');assert.equal(latest().twentyReply.p95Ms,300);
  step=1;
  await elements.run.onclick();
  assert.equal(latest().status,'pass');assert.equal(latest().twentyReply.p95Ms,1);
  assert.equal(latest().loadAttempt,3);assert.equal(latest().replayAttempt,3);
  const trials=history();assert.equal(trials.length,5);
  assert.deepEqual(trials.map(t=>t.status),['fail','fail','fail','fail','pass']);
  assert.equal(trials[3].twentyReply.p95Ms,300,'Passing rerun overwrote failed timing');
  console.log('Benchmark failure, retry and trial-retention checks passed.');
})().catch(error=>{console.error(error);process.exitCode=1});
