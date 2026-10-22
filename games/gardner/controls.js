// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
const GARDNER_UI=typeof module!=='undefined'?require('../shared/game-controls.js'):{gameText,gameSignal,createFontGame};
function gardnerText(source){
  return GARDNER_UI.gameText(source+' '.repeat(64*(Array.from(source).length+1)));
}
function createGardnerPlayground(){
  const get=id=>document.querySelector('#'+id);
  return GARDNER_UI.createFontGame({
    family:'GardnerOpponent',encode:gardnerText,limit:2048,accepted:[1,2,3,7],
    newGame:()=>{get('from').value='B4';get('to').value='A3';get('promotion').value='';return 'b';},
    move:()=>get('from').value+get('to').value+get('promotion').value+';',
    tests:[['b',1],['bA1A1;',4],['bgarbage',5]],
    messages:[
      'The font did not return a status. Enable standard ligatures.',
      'Your turn as Black. Choose a piece and its destination.',
      'The font wins by checkmate. Undo to try another move.',
      'You win by checkmate.',
      'Invalid move. The display is a partial replay.',
      'Malformed history. Start with b, then moves such as B4A3; with uppercase coordinates and a semicolon.',
      'The font could not complete the game. Start a new game.',
      'Draw. Start a new game, or undo to explore another reply.',
    ],
    moveErrors:{4:'Move rejected. Select a legal Black move and the appropriate promotion piece.'},
  });
}
if(typeof module!=='undefined')module.exports={createGardnerPlayground,gardnerText,gardnerSignal:GARDNER_UI.gameSignal};
