// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
const MU_TORERE_UI=typeof module!=='undefined'?require('../shared/game-controls.js'):{gameText,gameSignal,createFontGame};
function createMuTorerePlayground(){
  return MU_TORERE_UI.createFontGame({
    family:'MuTorerePerfect',limit:4096,accepted:[1,2,3,7],
    newGame:()=>document.querySelector('#setup').value,
    move:()=>document.querySelector('#point').value,
    tests:[['h',1],['b',1],['h2',4],['bad',5],['h=',7],['w817',3]],
    messages:[
      'The font did not return a status. Enable standard ligatures.',
      'Your turn. Choose a solid red counter that can slide to the empty point.',
      'The font wins: all your counters are trapped. Undo to try another move.',
      'You win: all the font’s counters are trapped.',
      'Invalid move or declined draw offer. The display is a partial replay.',
      'Malformed history. Start with h, b, w, or l, then point numbers 1–9. The display is a partial replay.',
      'The font could not complete the game. Start a new game.',
      'Draw agreed. Neither side needs to continue the loop.',
    ],
    moveErrors:{4:'Move rejected: that counter cannot reach the empty point, or the font declined your draw offer because it can force a win.'},
  });
}
if(typeof module!=='undefined')module.exports={createMuTorerePlayground,muTorereText:MU_TORERE_UI.gameText,
  muTorereSignal:width=>MU_TORERE_UI.gameSignal(width,1800,7)};
