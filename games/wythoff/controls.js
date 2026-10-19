// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
const WYTHOFF_UI = typeof module !== 'undefined' ? require('../shared/game-controls.js') : {gameText, gameSignal, createFontGame};
function createWythoffPlayground() {
  const get = id => document.querySelector('#'+id);
  const two = id => get(id).value ? get(id).value.padStart(2,'0') : '';
  return WYTHOFF_UI.createFontGame({
    family:'WythoffPerfect',limit:1024,
    newGame:()=>get('first').value+two('startA')+','+two('startB')+';',
    move:()=>get('heap').value+two('amount')+';',
    tests:[['b31,47;',1],['h01,02;A03;',4],['bad',5],['b01,01;',2]],
    messages:[
      'The font did not return a status. Enable standard ligatures.',
      'Your turn. Take tokens from one heap, or the same number from both.',
      'The font wins: it took the last tokens. Undo to try another move.',
      'You win: you took the last tokens.',
      'Invalid move or empty starting position. The display is a partial replay.',
      'Malformed history. Use a header such as b31,47; and moves such as A03;. The display is a partial replay.',
      'The font could not find a strategy move. Reset the game.',
    ],
    moveErrors:{4:'Move rejected: there are not enough tokens in the selected heap or heaps.',
                5:'Move rejected: use a whole number from 1 to 63.'},
  });
}
if (typeof module !== 'undefined') module.exports = {
  createWythoffPlayground, wythoffText:WYTHOFF_UI.gameText, wythoffSignal:WYTHOFF_UI.gameSignal,
};
