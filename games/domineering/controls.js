// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
const DOMINEERING_UI=typeof module!=='undefined'?require('../shared/game-controls.js'):{createFontGame};
function createDomineeringPlayground(){
  const get=id=>document.querySelector('#'+id);
  return DOMINEERING_UI.createFontGame({
    family:'DomineeringPerfect',limit:1024,
    newGame:()=>{
      const mode=get('setup').value;
      [get('column').value,get('row').value,get('direction').value]=mode==='h'?['A','2','V']:['A','1','H'];
      return mode;
    },
    move:()=>get('column').value+get('row').value+get('direction').value+';',
    tests:[['h',1],['b',1],['hA1H;',4],['hA1V',5]],
    messages:[
      'The font did not return a status. Enable standard ligatures.',
      'Your turn. Place your domino on two neighboring empty cells.',
      'The font wins. You have no legal placement.',
      'You win. The font has no legal placement.',
      'Invalid placement. Check orientation, overlap and board edges.',
      'Malformed history. Use h or b, then placements such as A1V;.',
      'The font could not complete the game. Start a new game.',
    ],
    moveErrors:{4:'Move rejected: use your side’s orientation on two empty cells within the board.'},
  });
}
if(typeof module!=='undefined')module.exports={createDomineeringPlayground};
