// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
(function (root) {
  'use strict';
  const EXAMPLES = {
    ethanol: 'CCO', acid: 'CC(=O)O', branched: 'CC(C)CO',
    nested: 'CC(C(O)N)O', cyclohexane: 'C1CCCCC1', benzene: 'c1ccccc1', kekule: 'C1=CC=CC=C1', pyridine: 'c1ccncc1', thiophene: 'c1ccsc1',
    pyrrole: '[nH]1cccc1', ammonium: '[NH4+]', acetate: 'CC(=O)[O-]', salt: '[NH4+].[Cl-]', fragments: 'CCO.C1CC1',
    nitrile: 'CC#N', halogens: 'ClCCBr', reused: 'C1CC1C1CC1', fused: 'C12CC1CC2', spiro: 'C12(CCC1)CCC2',
  };
  function validate(source, supportedTopologies = null) {
    if (!source) throw new Error('Enter a SMILES string.');
    if (source.length > 100) throw new Error('Keep the input below 100 characters.');
    if (/\s/.test(source)) throw new Error('Use one SMILES string without spaces or line breaks.');
    const parts = source.split('.');
    if (parts.some(part => !part)) throw new Error('Put a complete fragment on each side of a dot.');
    const fragments = parts.map(part => validateFragment(part,supportedTopologies));
    const atoms = fragments.reduce((sum,fragment) => sum + fragment.atoms,0);
    if (atoms > 10) throw new Error('The font supports up to 10 atoms across all fragments.');
    return {source,input:'{'+source+'}',atoms,fragments:parts.length,
      topology:fragments.length===1 ? fragments[0].topology : null,
      topologies:fragments.map(fragment=>fragment.topology)};
  }
  function validateFragment(source, supportedTopologies) {
    if (!source) throw new Error('Enter a SMILES string.');
    if (source.length > 100) throw new Error('Keep the input below 100 characters.');
    if (/\s/.test(source)) throw new Error('Use one SMILES string without spaces or line breaks.');
    const tokens = source.match(/\[(?:Cl|Br|[BCNOPSFIHbcnops])(?:H[0-4]?)?(?:[+-][1-3]?|\+{2,3}|-{2,3})?\]|Cl|Br|[BCNOPSFIHbcnops123()=#-]/g) || [];
    if (tokens.join('') !== source) {
      throw new Error('Supported atoms: B C N O P S F Cl Br I H and aromatic b c n o p s. Brackets allow H or H0–H4 and charges ±1–3 (for example [nH], [NH4+], [O-]). Isotopes, atom maps and stereochemistry are outside this prototype. Separate complete fragments with a dot.');
    }
    let count = 0, current = null, bond = null, expectAtom = true;
    const stack = [], rings = new Map(), edges = new Set(), positions = [], graph = [];
    let hasRing = false;
    function connect(a, b) {
      const key = [a,b].sort((x,y)=>x-y).join(',');
      if (a === b || edges.has(key)) throw new Error('A ring must join two distinct atoms without an existing bond.');
      edges.add(key);
    }
    for (const [event, token] of tokens.entries()) {
      if (/^(?:[A-Za-z]|\[)/.test(token)) {
        if (++count > 10) throw new Error('The font supports up to 10 atoms.');
        positions.push(stack.length);
        if (current !== null) {
          connect(current,count-1);
          graph.push({event, edge:[current,positions[current],count-1,stack.length,0]});
        }
        current = count-1; bond = null; expectAtom = false;
      } else if (/^[-=#]$/.test(token)) {
        if (current === null || bond !== null) throw new Error('Place one bond between atoms, or before a closing ring digit.');
        bond = token; expectAtom = true;
      } else if (token === '(') {
        if (expectAtom || current === null) throw new Error('Start a branch after an atom.');
        if (stack.length === 2) throw new Error('The font supports two nested branch levels.');
        stack.push(current); expectAtom = true;
      } else if (token === ')') {
        if (expectAtom || !stack.length) throw new Error('Close a non-empty branch with ).');
        current = stack.pop();
      } else {
        if (current === null || (expectAtom && bond === null)) throw new Error('Place a ring digit after an atom.');
        if (rings.has(token)) {
          const opening = rings.get(token);
          connect(opening.atom,current);
          graph.push({event:opening.event,edge:[opening.atom,positions[opening.atom],current,positions[current],1]});
          rings.delete(token); hasRing = true;
          bond = null; expectAtom = false;
        } else {
          if (bond !== null) throw new Error('Specify a ring bond at the closing digit, not the opening digit.');
          rings.set(token,{atom:current,event});
        }
      }
    }
    if (expectAtom) throw new Error('Finish the atom or bond expression.');
    if (stack.length) throw new Error('Close each branch with ).');
    if (rings.size) throw new Error('Use each open ring digit twice to close the ring.');
    const topology = JSON.stringify(graph.sort((a,b)=>a.event-b.event).map(item=>item.edge));
    if (hasRing && supportedTopologies && !supportedTopologies.has(topology)) {
      throw new Error('This ring arrangement is outside the font’s current layouts. Try a simple 3–10 member ring, a ring with one side chain, two linked rings, or a supported fused or spiro pair.');
    }
    return { source, input: '{' + source + '}', atoms: count, topology };
  }
  async function createPlayground(doc = document) {
    const source = doc.querySelector('#source'), drawing = doc.querySelector('#drawing');
    const status = doc.querySelector('#status'), raw = doc.querySelector('#raw');
    const examples = doc.querySelector('#examples');
    let loaded = false, supportedTopologies = null;
    const measure = doc.createElement('canvas').getContext('2d');
    measure.font = '1000px SMILESDiagrams';
    measure.fontKerning = 'none';
    function update() {
      drawing.textContent = ''; raw.textContent = '';
      try {
        const result = validate(source.value,supportedTopologies);
        if (!loaded) { status.textContent = 'Loading SMILES font…'; return; }
        drawing.textContent = result.input; raw.textContent = result.input;
        // Fit the font's ink bounds; no atom coordinates are calculated here.
        const ink = measure.measureText(result.input);
        const left = -ink.actualBoundingBoxLeft - 45;
        const top = 1650 - ink.actualBoundingBoxAscent - 45;
        const width = ink.actualBoundingBoxLeft + ink.actualBoundingBoxRight + 90;
        const height = ink.actualBoundingBoxAscent + ink.actualBoundingBoxDescent + 90;
        if ([left, top, width, height].every(Number.isFinite) && width > 0 && height > 0) {
          drawing.ownerSVGElement.setAttribute('viewBox', `${left} ${top} ${width} ${height}`);
        }
        status.textContent = result.atoms + (result.atoms === 1 ? ' atom' : ' atoms') + (result.fragments > 1 ? ' · ' + result.fragments + ' fragments' : '') + ' · drawn by the font. Chemical valence and stereochemistry are not checked.';
        source.removeAttribute('aria-invalid');
      } catch (error) {
        status.textContent = error.message; source.setAttribute('aria-invalid','true');
      }
    }
    source.addEventListener('input', update);
    examples.addEventListener('change', () => { source.value = EXAMPLES[examples.value]; update(); });
    update();
    try {
      const [faces,response] = await Promise.all([
        doc.fonts.load('1000px SMILESDiagrams'),
        fetch('./smiles-font.topologies.json?v=1.8.1'),
      ]);
      if (!response.ok) throw new Error('Layout list unavailable');
      supportedTopologies = new Set((await response.json()).map(item=>JSON.stringify(item)));
      if (!faces.length) throw new Error('Font unavailable');
      loaded = true; update();
    } catch (_) { status.textContent = 'Could not load the font. Serve the repository with python3 -m http.server 8000 and reload.'; }
  }
  if (typeof module === 'object' && module.exports) module.exports = { validate, EXAMPLES };
  else root.createSmilesPlayground = createPlayground;
})(typeof globalThis === 'object' ? globalThis : this);
