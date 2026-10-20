// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
const NIM_UI=typeof module!=='undefined'?require('../shared/game-controls.js'):{gameText,gameSignal,createFontGame};
function createNimPlayground(){
  const get=id=>document.querySelector('#'+id);
  const two=id=>get(id).value?get(id).value.padStart(2,'0'):'';
  return NIM_UI.createFontGame({
    family:'NimPerfect',limit:1024,
    newGame:()=>get('first').value+get('rule').value+['startA','startB','startC'].map(two).join(',')+';',
    move:()=>get('heap').value+two('amount')+';',
    tests:[['bN03,05,07;',1],['hN01,00,00;A02;',4],['bad',5],['bM01,00,00;',3],['hM01,00,00;A01;',2]],
    messages:[
      'The font did not return a status. Enable standard ligatures.',
      'Your turn. Take a positive number of tokens from exactly one heap.',
      'The font wins under the selected last-token rule. Undo to try another move.',
      'You win under the selected last-token rule.',
      'Invalid take or empty starting position. The display is a partial replay.',
      'Malformed history. Use a header such as bN03,05,07; and moves such as A01;. The display is a partial replay.',
      'The font could not complete the game. Start a new game.',
    ],
    moveErrors:{4:'Take rejected: that heap does not contain enough tokens.',5:'Take rejected: use a whole number from 1 to 31.'},
  });
}
if(typeof module!=='undefined')module.exports={createNimPlayground,nimText:NIM_UI.gameText,nimSignal:NIM_UI.gameSignal};
