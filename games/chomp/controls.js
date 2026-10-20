// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
const CHOMP_UI=typeof module!=='undefined'?require('../shared/game-controls.js'):{createFontGame};
function createChompPlayground(){
  const get=id=>document.querySelector('#'+id);
  return CHOMP_UI.createFontGame({
    family:'ChompPerfect',limit:1024,
    newGame:()=>get('setup').value,
    move:()=>get('column').value+get('row').value+';',
    tests:[['h',1],['b',1],['hA1;',4],['hC3',5]],
    messages:[
      'The font did not return a status. Enable standard ligatures.',
      'Your turn. Choose a remaining chocolate square other than poisoned A1.',
      'The font wins. Only poisoned A1 remains.',
      'You win. Only poisoned A1 remains.',
      'Invalid bite. Choose a remaining square other than A1.',
      'Malformed history. Use h or b, then coordinates ending in a semicolon, such as C3;.',
      'The font could not complete the game. Start a new game.',
    ],
    moveErrors:{4:'Move rejected: choose a remaining square other than poisoned A1.'},
  });
}
if(typeof module!=='undefined')module.exports={createChompPlayground};
