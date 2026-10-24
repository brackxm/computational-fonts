// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
// History transport and font status only; no chess rules or move selection.
const RESEARCH_UI=typeof module!=='undefined'?require('../../shared/game-controls.js'):{gameText,createFontGame};
function researchText(source){
  return RESEARCH_UI.gameText(source+' '.repeat(256*(Array.from(source).length+1)));
}
function createResearchPlayground(){
  const get=id=>document.querySelector('#'+id);
  return RESEARCH_UI.createFontGame({
    family:'GardnerResearch',encode:researchText,limit:512,accepted:[1,2,3,6,7],
    newGame:()=>{get('from').value='B5';get('to').value='C3';get('promotion').value='';return 'b';},
    move:()=>get('from').value+get('to').value+get('promotion').value+';',
    tests:[['b',1],['bA1A1;',4],['bgarbage',5],['bB4A3;',6]],
    messages:[
      'The font did not return a status. Enable standard ligatures.',
      'Your turn as Black. Choose a piece and its destination.',
      'The font wins by checkmate. Undo to try another move.',
      'You win by checkmate.',
      'Invalid move. The display is a partial replay.',
      'Malformed history. Use uppercase coordinates and a semicolon.',
      'Unproved opening. This research font stops here. Undo or use the lightweight playable opponent.',
      'Draw. Start a new game, or undo to explore another reply.',
    ],
    moveErrors:{4:'Move rejected. Select a legal Black move and the appropriate promotion piece.'},
  });
}
if(typeof module!=='undefined')module.exports={createResearchPlayground,researchText};
