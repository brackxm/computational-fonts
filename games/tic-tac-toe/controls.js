// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
const TTT_UI=typeof module!=='undefined'?require('../shared/game-controls.js'):{gameText,gameSignal,createFontGame};
function createTicTacToePlayground(){
  const get=id=>document.querySelector('#'+id);
  return TTT_UI.createFontGame({
    family:'TicTacToePerfect',limit:512,accepted:[1,2,3,7],
    newGame:()=>get('setup').value,move:()=>get('square').value,
    tests:[['h',1],['h11',4],['bad',5],['h124',2],['h12768',7]],
    messages:[
      'The font did not return a status. Enable standard ligatures.',
      'Your turn. Choose an empty square numbered 1–9.',
      'The font wins. Undo to try another move.',
      'You win.',
      'That square is occupied. The display is a partial replay.',
      'Malformed history. Start with h or b and append your squares, numbered 1–9.',
      'The font could not complete the game. Start a new game.',
      'Draw. Neither player has three in a row.',
    ],
    moveErrors:{4:'Move rejected: that square is already occupied.'},
  });
}
if(typeof module!=='undefined')module.exports={createTicTacToePlayground,ticTacToeText:TTT_UI.gameText,
  ticTacToeSignal:width=>TTT_UI.gameSignal(width,1800,7)};
