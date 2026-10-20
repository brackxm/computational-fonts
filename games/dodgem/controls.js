// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
const DODGEM_UI=typeof module!=='undefined'?require('../shared/game-controls.js'):{createFontGame};
function createDodgemPlayground(){
  const get=id=>document.querySelector('#'+id);
  return DODGEM_UI.createFontGame({
    family:'DodgemPerfect',limit:1024,
    newGame:()=>{
      const mode=get('setup').value;
      [get('from').value,get('to').value]=mode==='h'?['A3','B3']:['B1','B2'];
      return mode;
    },
    move:()=>get('from').value+get('to').value+';',
    tests:[['h',1],['b',1],['hA1A2;',4],['hA3B3',5]],
    messages:[
      'The font did not return a status. Enable standard ligatures.',
      'Your turn. Move your car to an empty neighbor, or exit through your side’s edge.',
      'The font wins. Undo to try another move.',
      'You win. Both cars exited, or the font has no legal move.',
      'Invalid move. Check the car, destination and allowed directions.',
      'Malformed history. Use h or b, then moves such as A3B3; or C2X;.',
      'The font could not complete the game. Start a new game.',
      'Draw.',
    ],
    moveErrors:{4:'Move rejected: choose your car and an empty legal neighbor, or its exit.'},
  });
}
if(typeof module!=='undefined')module.exports={createDodgemPlayground};
