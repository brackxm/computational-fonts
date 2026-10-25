// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
const SIM_UI=typeof module!=='undefined'?require('../shared/game-controls.js'):{createFontGame};
function createSimPlayground(){
  const get=id=>document.querySelector('#'+id);
  return SIM_UI.createFontGame({
    family:'SimPerfect',limit:1024,
    newGame:()=>{
      const mode=get('setup').value;
      get('edge').value=mode==='b'?'AC':'AB';
      return mode;
    },
    move:()=>get('edge').value+';',
    tests:[['h',1],['b',1],['hAB;AB;',4],['hAB',5]],
    messages:[
      'The font did not return a status. Enable standard ligatures.',
      'Your turn. Choose an unused edge; avoid making a triangle in your own colour.',
      'The font wins: your edges completed a triangle. Undo to try another move.',
      'You win: the font completed a triangle.',
      'Invalid move. That edge is already coloured.',
      'Malformed history. Use h or b, then edges such as AB; or CF;.',
      'The font could not complete the game. Start a new game.',
      'Draw.',
    ],
    moveErrors:{4:'Move rejected: choose an unused edge.'},
  });
}
if(typeof module!=='undefined')module.exports={createSimPlayground};
