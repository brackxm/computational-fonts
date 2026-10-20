// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
const ACHI_UI=typeof module!=='undefined'?require('../shared/game-controls.js'):{createFontGame};
function createAchiPlayground(){
  const get=id=>document.querySelector('#'+id);
  return ACHI_UI.createFontGame({
    family:'AchiPerfect',limit:1024,accepted:[1,2,3,7],
    newGame:()=>{
      get('action').value='place';get('to').value='A1';
      return get('setup').value;
    },
    move:()=>get('action').value==='place'?get('to').value+';':get('from').value+get('to').value+';',
    tests:[['h',1],['b',1],['hA1A2;',4],['hA1;=',7],['b=',4],['hA1',5]],
    messages:[
      'The font did not return a status. Enable standard ligatures.',
      'Your turn. Place until all six counters are down, then slide along a board line.',
      'The font wins. Undo to try another move.',
      'You win with three counters in a straight row.',
      'Invalid move or declined draw. Check the phase, piece and board lines.',
      'Malformed history. Use h or b, then A1; to place or A1A2; to slide.',
      'The font could not complete the game. Start a new game.',
      'Draw agreed. The font had no forced win.',
    ],
    moveErrors:{4:'Move or draw rejected. Use the current phase and board lines; the font declines draws when it can force a win.'},
  });
}
if(typeof module!=='undefined')module.exports={createAchiPlayground};
