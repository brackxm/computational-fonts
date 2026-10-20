// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
const DOTS_UI=typeof module!=='undefined'?require('../shared/game-controls.js'):{createFontGame};
function createDotsAndBoxesPlayground(){
  const get=id=>document.querySelector('#'+id);
  return DOTS_UI.createFontGame({
    family:'DotsAndBoxesPerfect',limit:1024,accepted:[1,2,3,7],
    newGame:()=>{
      const mode=get('setup').value;
      [get('column').value,get('row').value,get('direction').value]=['A','1',mode==='h'?'H':'V'];
      return mode;
    },
    move:()=>get('column').value+get('row').value+get('direction').value+';',
    tests:[['h',1],['b',1],['hC3H;',4],['hA1H',5]],
    messages:[
      'The font did not return a status. Enable standard ligatures.',
      'Your turn. Draw one empty edge. Complete a box to claim it and play again.',
      'The font wins with more boxes.',
      'You win with more boxes.',
      'Invalid edge. It is already drawn or extends beyond the dot grid.',
      'Malformed history. Use h or b, then edges such as A1H; or B2V;.',
      'The font could not complete the game. Start a new game.',
      'Draw. Each side claimed two boxes.',
    ],
    moveErrors:{4:'Move rejected: choose an undrawn edge between neighboring dots.'},
  });
}
if(typeof module!=='undefined')module.exports={createDotsAndBoxesPlayground};
