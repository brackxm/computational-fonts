// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
const KAYLES_UI=typeof module!=='undefined'?require('../shared/game-controls.js'):{createFontGame};
function createKaylesPlayground(){
  const get=id=>document.querySelector('#'+id);
  return KAYLES_UI.createFontGame({
    family:'KaylesPerfect',limit:1024,
    newGame:()=>get('setup').value,
    move:()=>get('pin').value+get('kind').value+';',
    tests:[['h',1],['b',1],['h12D;',4],['h01S',5]],
    messages:[
      'The font did not return a status. Enable standard ligatures.',
      'Your turn. Remove one standing pin, or two originally adjacent standing pins.',
      'The font wins by taking the last pin.',
      'You win by taking the last pin.',
      'Invalid removal. Pins must still be standing and a pair must be adjacent.',
      'Malformed history. Use h or b, then moves such as 01S; or 06D;.',
      'The font could not complete the game. Start a new game.',
    ],
    moveErrors:{4:'Move rejected: choose a standing pin, or an adjacent standing pair within 01–12.'},
  });
}
if(typeof module!=='undefined')module.exports={createKaylesPlayground};
