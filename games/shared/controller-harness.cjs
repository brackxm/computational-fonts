// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
// Browser-controller test doubles delegate font measurement to real HarfBuzz.
const {execFileSync} = require('node:child_process');
function controllerHarness({font,create,values,moves=[],missing=false,incompatible=false,rejected=false}) {
  function element() {
    return {value:'',textContent:'',dataset:{},listeners:{},attributes:{},
      append() {},setAttribute(k,v){this.attributes[k]=v;},addEventListener(k,v){this.listeners[k]=v;},
      getBoundingClientRect(){
        if(incompatible)return {width:0};
        const glyphs=JSON.parse(execFileSync('hb-shape',[font,'--text='+this.textContent,'--output-format=json'],{encoding:'utf8',timeout:10000}));
        return {width:glyphs.reduce((s,g)=>s+g.ax,0)};
      },
    };
  }
  const ids=new Set(['record','drawing','status','reset','undo','play',...Object.keys(values)]);
  const e=Object.fromEntries(Array.from(ids,id=>[id,element()]));
  for(const [id,value] of Object.entries(values))e[id].value=value;
  const buttons=moves.map(move=>Object.assign(element(),{dataset:{move}}));
  global.document={body:{append(){}},createElement:element,querySelector:s=>e[s.slice(1)],querySelectorAll:()=>buttons,
    fonts:{load:async()=>{if(rejected)throw new Error('Load failed');return missing?[]:[{}];}}};
  return {session:create(),e,buttons,setIncompatible(v){incompatible=v;}};
}
module.exports={controllerHarness};
