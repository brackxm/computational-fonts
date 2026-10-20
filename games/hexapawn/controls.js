// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
const HEXAPAWN_UI=typeof module!=='undefined'?require('../shared/game-controls.js'):{gameText,gameSignal,createFontGame};
function createHexapawnPlayground(){
  const get=id=>document.querySelector('#'+id);
  return HEXAPAWN_UI.createFontGame({
    family:'HexapawnPerfect',limit:512,
    newGame:()=>{
      const mode=get('setup').value;
      // Static form examples; every submitted move is checked by the font.
      [get('from').value,get('to').value]=mode==='b'?['A3','B2']:['B1','B2'];
      return mode;
    },
    move:()=>get('from').value+get('to').value,
    tests:[['h',1],['b',1],['hA1A3',4],['bad',5],['bA3B2C3C2C2C1',3]],
    messages:[
      'The font did not return a status. Enable standard ligatures.',
      'Your turn. Advance one square, or capture one square diagonally forward.',
      'The font wins. Undo to try another move.',
      'You win. You beat perfect play from its losing starting side.',
      'Invalid move. The display is a partial replay.',
      'Malformed history. Use h or b, then moves such as B1B2. The display is a partial replay.',
      'The font could not complete the game. Start a new game.',
    ],
    moveErrors:{4:'Move rejected: choose your pawn, then a legal forward step or diagonal capture.'},
  });
}
if(typeof module!=='undefined')module.exports={createHexapawnPlayground,hexapawnText:HEXAPAWN_UI.gameText,hexapawnSignal:HEXAPAWN_UI.gameSignal};
