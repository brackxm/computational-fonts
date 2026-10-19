// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
const CRAM_UI=typeof module!=='undefined'?require('../shared/game-controls.js'):{gameText,gameSignal,createFontGame};
function createCramPlayground(){
  const get=id=>document.querySelector('#'+id);
  return CRAM_UI.createFontGame({
    family:'CramPerfect',limit:256,newGame:()=>'b',
    move:()=>get('cell').value+get('direction').value,
    tests:[['b',1],['bA1H',1],['bC3H',4],['bad',5]],
    messages:[
      'The font did not return a status. Enable standard ligatures.',
      'Your turn. Place a domino across two empty neighboring squares.',
      'The font wins: there is no legal placement left. Undo to try another move.',
      'You win.',
      'Invalid placement: a square is occupied or the domino leaves the board. The display is a partial replay.',
      'Malformed history. Start with b, then moves such as A1H or B2V. The display is a partial replay.',
      'The font could not place its reply. Reset the game.',
    ],
    moveErrors:{4:'Placement rejected: choose two empty squares inside the board.'},
  });
}
if(typeof module!=='undefined')module.exports={createCramPlayground,cramText:CRAM_UI.gameText,cramSignal:CRAM_UI.gameSignal};
