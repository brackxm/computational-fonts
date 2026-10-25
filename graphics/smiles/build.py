# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Build a bounded SMILES graph renderer implemented with native OpenType shaping."""

import argparse
import math
import json
from functools import partial
from io import StringIO
from pathlib import Path
import sys

from fontTools.feaLib.builder import Builder
from fontTools.fontBuilder import FontBuilder
from fontTools.otlLib.builder import (buildCoverage, buildLookup, buildLigatureSubstSubtable,
                                      buildMultipleSubstSubtable)
from fontTools.ttLib.tables import otTables
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.recordingPen import DecomposingRecordingPen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'decoders/shared'))
from font_metadata import DEFAULT_BASE, load_base_font, mark_modified_font, replace_font_names, compact_glyphs, compact_contours

MAX_ATOMS, MAX_DEPTH = 10, 2
# Each atom needs one clock tick. Sibling branch openings and consecutive
# returns together need at most one additional tick per branch (<= atoms-1).
# BOND runs after PUSH and POP, so explicit branch/return bonds add no ticks.
PASSES = 2*MAX_ATOMS
CELL, WIDTH, HEIGHT = 165, 2400, 1650
AROMATIC_ELEMENTS = 'bcnops'
ELEMENTS = ('B', 'C', 'N', 'O', 'P', 'S', 'F', 'Cl', 'Br', 'I', 'H')
PALETTE = ('263b42', '2563eb', 'cf394b', 'ad6c18', '178251', '7852a3')
ELEMENT_COLOR = {'N': 1, 'O': 2, 'P': 3, 'S': 3, 'F': 4, 'Cl': 4, 'Br': 3, 'I': 5}


def point(index, depth):
    return 110 + index * CELL, 790 - depth * 300 + (index % 2) * 95


def polygon(pen, points):
    pen.moveTo(points[0])
    for p in points[1:]:
        pen.lineTo(p)
    pen.closePath()


def stroke(pen, start, end, width=9):
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    if not length:
        return
    ox, oy = -dy * width / length / 2, dx * width / length / 2
    polygon(pen, [(start[0]+ox, start[1]+oy), (end[0]+ox, end[1]+oy),
                  (end[0]-ox, end[1]-oy), (start[0]-ox, start[1]-oy)])


def chemical_bond(p, q, order, clip_start=0, clip_end=0, inward=0, inner_only=False, *, label_bounds=None):
    from clearance import label_clearance
    if (clip_start or clip_end) and label_bounds is None:
        raise ValueError('Labeled bonds require font label bounds')
    pen = TTGlyphPen(None)
    dx,dy = q[0]-p[0],q[1]-p[1]
    length = math.hypot(dx,dy)
    if length < 1:
        return pen.glyph()
    ux,uy = dx/length,dy/length
    # Aromatic edges are solid; the rendering stage emits a circle per ring.
    order = 1 if order in (4,5) else order
    offsets = [0, inward*28] if order==2 and inward else [(k-(order-1)/2)*22 for k in range(order)]
    for k,offset in enumerate(offsets):
        if inner_only and k==0:
            continue
        inset = 27 if order==2 and inward and k else 0
        normal=(-uy*offset,ux*offset)
        start_gap=label_clearance(label_bounds,(ux,uy),normal) if clip_start else 0
        end_gap=label_clearance(label_bounds,(-ux,-uy),normal) if clip_end else 0
        start = (p[0]+ux*(start_gap+inset)+normal[0], p[1]+uy*(start_gap+inset)+normal[1])
        end = (q[0]-ux*(end_gap+inset)+normal[0], q[1]-uy*(end_gap+inset)+normal[1])
        stroke(pen,start,end,9)
    return pen.glyph()


def bond_glyph(a, b, order, ring=0):
    return chemical_bond(point(*a),point(*b),order)


def error_glyph():
    pen = TTGlyphPen(None)
    stroke(pen, (20, 1030), (60, 1070), 9)
    stroke(pen, (20, 1070), (60, 1030), 9)
    return pen.glyph()


def build_font(output):
    output = Path(output)
    base = load_base_font(DEFAULT_BASE, output)
    source = base.getGlyphSet()
    scale = 1000 / base['head'].unitsPerEm
    glyphs, metrics, colors = {}, {}, {}
    def add(name, glyph=None, advance=0, color=None):
        if name in glyphs:
            return name
        glyph = glyph if glyph is not None else TTGlyphPen(None).glyph()
        glyph.recalcBounds(glyphs)
        glyphs[name] = glyph
        metrics[name] = (advance, getattr(glyph, 'xMin', 0))
        if color is not None:
            colors[name] = [(name, color)]
        return name
    add('.notdef', error_glyph(), 600)
    chars = {}
    for code in range(32, 127):
        name = f'u{code:04X}'
        original = base.getBestCmap()[code]
        # Decompose components before using a new glyph set.
        recording = DecomposingRecordingPen(source)
        source[original].draw(recording)
        pen = TTGlyphPen(None)
        recording.replay(TransformPen(pen, (scale, 0, 0, scale, 0, 0)))
        add(name, pen.glyph(), round(base['hmtx'][original][0]*scale))
        chars[chr(code)] = name
    hidden = add('hidden')
    end = add('end', advance=WIDTH)
    initial = add('initial', error_glyph())
    origin = add('origin')
    marks = [hidden,origin]
    atom_chars, atom_names = {}, {}
    def text_width(text, size):
        return sum(base['hmtx'][base.getBestCmap()[ord(c)]][0] for c in text)*size/base['head'].unitsPerEm
    def draw_text(pen, text, x, y, size):
        factor = size/base['head'].unitsPerEm
        for char in text:
            recording = DecomposingRecordingPen(source)
            original = base.getBestCmap()[ord(char)]
            source[original].draw(recording)
            recording.replay(TransformPen(pen,(factor,0,0,factor,x,y)))
            x += base['hmtx'][original][0]*factor
    def label_glyph(element, position, explicit_carbon=False):
        element = element.upper() if element.islower() else element
        pen = TTGlyphPen(None)
        if element.startswith('[') or (element == 'C' and not explicit_carbon):
            return pen.glyph()
        x,y = position
        draw_text(pen,element,x-text_width(element,110)/2,y-40,110)
        return pen.glyph()
    # One conservative envelope covers every element body, including Cl/Br.
    # Keeping a shared envelope preserves the bounded binary clipping classes
    # while deriving clearance from the source font and each stroke's direction.
    label_boxes=[]
    for element in ELEMENTS:
        glyph=label_glyph(element,(0,0),True)
        glyph.recalcBounds(glyphs)
        label_boxes.append((glyph.xMin,glyph.yMin,glyph.xMax,glyph.yMax))
    label_bounds=tuple((min if i<2 else max)(box[i] for box in label_boxes) for i in range(4))
    label_bond=partial(chemical_bond,label_bounds=label_bounds)
    def bracket_glyph(element, hydrogens, charge, direction):
        element = element.upper() if element.islower() else element
        pen = TTGlyphPen(None)
        decorations = []
        def decoration(text, x, y, size):
            part_pen = TTGlyphPen(None)
            draw_text(part_pen,text,x,y,size)
            part = part_pen.glyph()
            part.recalcBounds(glyphs)
            if part.numberOfContours:
                decorations.append((part.xMin,part.yMin,part.xMax,part.yMax))
                part.draw(pen,glyphs)
        half = text_width(element,110)/2
        draw_text(pen,element,-half,-40,110)
        right,top,left = half,40,-half
        if hydrogens:
            count = str(hydrogens) if hydrogens>1 else ''
            hwidth = text_width('H',110)+text_width(count,70)
            hx,hy = {'R':(half+8,-40),'L':(-half-8-hwidth,-40),
                     'U':(-hwidth/2,70),'D':(-hwidth/2,-150)}[direction]
            if charge and direction=='D':
                # Center the complete H/charge group in the open sector.
                # Raise the sign beside H without putting it beside the atom,
                # where a descending bond can cross it.
                group_width = hwidth+5+text_width(BracketAtoms.charge_text(charge),65)
                hx = -group_width/2
                hy = -165-max(0,group_width/2-59)
            decoration('H',hx,hy,110)
            decoration(count,hx+text_width('H',110),hy-22,70)
            right,top,left = max(right,hx+hwidth),max(top,hy+80),min(left,hx)
        if charge:
            # The sign follows the magnitude in a conventional superscript.
            text = BracketAtoms.charge_text(charge)
            cx,cy = right+5,top+6
            if direction=='L':
                cx = left-text_width(text,65)-5
            elif direction=='D' and hydrogens:
                cx,cy = hx+hwidth+5,hy+45
            elif direction=='U' and not hydrogens:
                cx,cy = -text_width(text,65)/2,85
            decoration(text,cx,cy,65)
        return pen.glyph(),decorations
    from brackets import BracketAtoms
    brackets = BracketAtoms(add,marks,chars,metrics,glyphs,bracket_glyph,ELEMENTS,AROMATIC_ELEMENTS)
    for element in ELEMENTS:
        fallback = TTGlyphPen(glyphs)
        advance = 0
        for char in element:
            fallback.addComponent(chars[char], (1, 0, 0, 1, advance, 0))
            advance += metrics[chars[char]][0]
        token = add('input_' + element, fallback.glyph(), advance)
        atom_chars[element] = token
        for n in range(MAX_ATOMS):
            for d in range(MAX_DEPTH+1):
                name = f'atom_{element}_{n}_{d}'
                atom_names[element,n,d] = name
                marks.append(add(name,label_glyph(element,point(n,d)),color=ELEMENT_COLOR.get(element,0)))
    aromatic_flags = {}
    for element in AROMATIC_ELEMENTS:
        aromatic_flags[element] = add('aromatic_input_'+element)
        marks.append(aromatic_flags[element])
        for n in range(MAX_ATOMS):
            for d in range(MAX_DEPTH+1):
                name = f'atom_{element}_{n}_{d}'
                atom_names[element,n,d] = name
                marks.append(add(name,label_glyph(element,point(n,d)),color=ELEMENT_COLOR.get(element.upper(),0)))
    for element in (*ELEMENTS,*AROMATIC_ELEMENTS):
        for n in range(MAX_ATOMS):
            for d in range(MAX_DEPTH+1):
                name = add(f'atom_bracket_{element}_{n}_{d}')
                atom_names['['+element+']',n,d] = name
                marks.append(name)
    states, classes, normal = {}, {}, []
    def state(n, last, depth, bond=0, pending=False):
        key = (n, last, depth, bond, pending)
        return states[key]
    for n in range(1, MAX_ATOMS+1):
        for last in range(n):
            for d in range(MAX_DEPTH+1):
                for bond in range(4):
                    for pending in (False, True) if d else (False,):
                        name = f'{"p" if pending else "s"}_{n}_{last}_{d}_{bond}'
                        states[n,last,d,bond,pending] = add(name, error_glyph())
                        if not pending:
                            classes.setdefault((last,d,bond), []).append(name)
                            normal.append(name)
    features = ['languagesystem DFLT dflt;', 'languagesystem latn dflt;']
    expansions = {}
    def lookup(name, rules, flags='IgnoreMarks'):
        features.append(f'lookup {name} useExtension {{ lookupflag {flags};')
        for rule in rules:
            features.append(rule)
            if "'" in rule:
                features.append('subtable;')
        features.append(f'}} {name};')
    brackets.parser_lookups(lookup,atom_chars,initial,list(states.values()),atom_names,state,hidden)
    lookup('TOKENIZE_AROMATIC',[
        f'sub {chars[e]} by {atom_chars[e.upper()]} {aromatic_flags[e]};'
        for e in AROMATIC_ELEMENTS
    ],'0')
    # Tokenization is lexical only; no molecule is precomputed by the host.
    lookup('TOKENIZE', [f'sub {" ".join(chars[c] for c in e)} by {atom_chars[e]};'
                        for e in sorted(ELEMENTS, key=len, reverse=True)], '0')
    lookup('INIT', [f'sub {chars["{"]} by {origin} {initial};'], '0')
    atom_rules, bond_rules, push_rules, open_rules = [], [], [], {i: [] for i in range(1,4)}
    saved, rings = {}, {i: {} for i in range(1,4)}
    bond_records = {}
    def drawbond(a,b,order,ring=0,signal=False):
        # A closed ring no longer needs its source digit in the draw tape.
        # Canonicalize aliases to share glyphs across 1/2/3 closures.
        ring = int(bool(ring))
        prefix = 'signal' if signal else 'bond'
        name = f'{prefix}_{a[0]}_{a[1]}_{b[0]}_{b[1]}_{order}_{ring}'
        if name not in glyphs:
            marks.append(add(name, None if signal else bond_glyph(a,b,order,ring), color=None if signal else 0))
            if not signal:
                bond_records[name] = (a,b,order,ring)
        return name
    for last in range(MAX_ATOMS):
        for d in range(MAX_DEPTH+1):
            saved[last,d] = add(f'saved_{last}_{d}', error_glyph())
            marks.append(saved[last,d])
            for ring in rings:
                rings[ring][last,d] = add(f'ring_{ring}_{last}_{d}', error_glyph())
                marks.append(rings[ring][last,d])
    for element, token in atom_chars.items():
        name = add('first_' + element)
        atom_rules.append(f'sub {initial} {token} by {name};')
        expansions[name] = [f'atom_{element}_0_0', state(1,0,0)]
    for (n,last,d,bond,pending), current in states.items():
        if n < MAX_ATOMS:
            for element, token in atom_chars.items():
                name = add(f'emit_{element}_{current}')
                atom_rules.append(f'sub {current} {token} by {name};')
                line = drawbond((last,d-int(pending)), (n,d), (5 if bond==1 else max(1,bond)))
                expansions[name] = [line, f'atom_{element}_{n}_{d}', state(n+1,n,d)]
        if bond == 0:
            for char, order in (('-',1), ('=',2), ('#',3)):
                bond_rules.append(f'sub {current} {chars[char]} by {state(n,last,d,order,pending)};')
            if not pending and d < MAX_DEPTH and n < MAX_ATOMS:
                token = add('push_' + current)
                push_rules.append(f'sub {current} {chars["("]} by {token};')
                expansions[token] = [saved[last,d], state(n,last,d+1,0,True)]
            if not pending:
                for ring in rings:
                    token = add(f'open_{ring}_{current}')
                    open_rules[ring].append(f'sub {current} {chars[str(ring)]} by {token};')
                    expansions[token] = [rings[ring][last,d], current]
    aromatic_labels = []
    for e in AROMATIC_ELEMENTS:
        for n in range(MAX_ATOMS):
            for d in range(MAX_DEPTH+1):
                aromatic_labels.append(
                    f"sub {atom_names[e.upper(),n,d]}' {state(n+1,n,d)} {aromatic_flags[e]} by {atom_names[e,n,d]};")
    lookup('AROMATIC_LABEL',aromatic_labels,
           'UseMarkFilteringSet ['+' '.join([*atom_names.values(),*aromatic_flags.values()])+']')
    lookup('AROMATIC_FLAG_EAT',[
        f"sub [{' '.join(atom_names[e,n,d] for n in range(MAX_ATOMS) for d in range(MAX_DEPTH+1))}] "
        f"[{' '.join(normal)}] {aromatic_flags[e]}' by {hidden};"
        for e in AROMATIC_ELEMENTS
    ],'UseMarkFilteringSet ['+' '.join([*atom_names.values(),*aromatic_flags.values()])+']')
    lookup('ATOM', atom_rules[:1])
    lookup('BOND', bond_rules)
    lookup('PUSH', push_rules)
    # A saved branch origin is the nearest mark admitted by this filter.
    features.append('@SAVED = [' + ' '.join(saved.values()) + '];')
    pop_signals = {key: add(f'pop_{key[0]}_{key[1]}') for key in saved}
    marks.extend(pop_signals.values())
    features.append('@POP = [' + ' '.join(pop_signals.values()) + '];')
    pop_mark, pop_return = [], []
    for (origin,d), marker in saved.items():
        if d == MAX_DEPTH:
            continue
        valid = [state(n,last,d+1) for n in range(origin+2, MAX_ATOMS+1)
                 for last in range(origin+1,n)]
        if valid:
            pop_mark.append(f'sub {marker}\' [{" ".join(valid)}] {chars[")"]} by {pop_signals[origin,d]};')
        for n in range(origin+2,MAX_ATOMS+1):
            valid = [state(n,last,d+1) for last in range(origin+1,n)]
            pop_return.append(f'sub {pop_signals[origin,d]} [{" ".join(valid)}]\' {chars[")"]} by {state(n,origin,d)};')
    pop_flags = 'UseMarkFilteringSet [@SAVED @POP]'
    lookup('POP_MARK', pop_mark, pop_flags)
    lookup('POP_RETURN', pop_return, pop_flags)
    # Keep the consumed parenthesis as a non-mark barrier until POP_EAT
    # finishes scanning, so the same return cannot also consume the next ')'.
    closed_branch=add('closed_branch')
    lookup('POP_EAT', [f"sub @POP [{' '.join(normal)}] {chars[')']}' by {closed_branch};"], pop_flags)
    lookup('POP_HIDE', [f'sub @POP by {hidden};',f'sub {closed_branch} by {hidden};'], '0')
    for ring, markers in rings.items():
        close, signals = [], {}
        features.append(f'@RING{ring} = [' + ' '.join(markers.values()) + '];')
        for (last,d,bond), members in classes.items():
            mapping = []
            for a, marker in markers.items():
                if a[0] >= last:
                    continue
                signal = drawbond(a,(last,d),(5 if bond==1 else max(1,bond)),ring,True)
                signals[signal] = drawbond(a,(last,d),(5 if bond==1 else max(1,bond)),ring)
                mapping.append(f'sub {marker} by {signal};')
            if not mapping:
                continue
            name = f'MAP_{ring}_{last}_{d}_{bond}'
            lookup(name, mapping, '0')
            close.append(f"sub @RING{ring}' lookup {name} [{' '.join(members)}] {chars[str(ring)]};")
        features.append(f'@SIGNAL{ring} = [' + ' '.join(signals) + '];')
        flags = f'UseMarkFilteringSet [@RING{ring} @SIGNAL{ring}]'
        lookup(f'CLOSE{ring}', close, flags)
        lookup(f'RESET{ring}', [
            f"sub @SIGNAL{ring} {current}' {chars[str(ring)]} by {state(n,last,d)};"
            for (n,last,d,bond,pending), current in states.items() if bond and not pending
        ], flags)
        lookup(f'EAT{ring}', [f"sub @SIGNAL{ring} [{' '.join(normal)}] {chars[str(ring)]}' by {hidden};"], flags)
        lookup(f'HIDE{ring}', [f'sub {s} by {b};' for s,b in signals.items()], '0')
        lookup(f'OPEN{ring}', open_rules[ring])
    lookup('EXPAND', [f'sub {name} by {" ".join(result)};' for name,result in list(expansions.items())[:1]], '0')
    from fragments import parser as fragment_parser, spacing as fragment_spacing
    fragment_counts = fragment_parser(add,lookup,chars,states,MAX_ATOMS)
    lookup('END', [f'sub {state(n,last,0)} {chars["}"]} by {end};'
                   for n in range(1,MAX_ATOMS+1) for last in range(n)])
    from rendering import compile_rendering
    render_cycle, layouts, manual_contexts = compile_rendering(
        add, marks, features, lookup, atom_names, bond_records, label_glyph,
        label_bond, point, WIDTH, brackets)
    fragment_spacing(features,fragment_counts,layouts,WIDTH,point)
    if len(glyphs) > 65535:
        raise ValueError(f'Too many glyphs: {len(glyphs)}')
    features.append('@MARKS = [' + ' '.join(marks) + '];')
    features.append('table GDEF { GlyphClassDef , , @MARKS, ; } GDEF;')
    # Distinct wrapper lookup indices make every shaping pass execute, while
    # sharing the transition data. Repeated feature indices are deduplicated
    # by shapers, so simply repeating lookup references is insufficient.
    cycle = ['BRACKET_START','ATOM','EXPAND','BRACKET_LABEL','BRACKET_FLAG_EAT','AROMATIC_LABEL','AROMATIC_FLAG_EAT','PUSH','EXPAND', 'POP_MARK','POP_RETURN','POP_EAT','POP_HIDE','BOND']
    for ring in rings:
        cycle.extend([f'CLOSE{ring}',f'RESET{ring}',f'EAT{ring}',f'HIDE{ring}',f'OPEN{ring}','EXPAND'])
    cycle.extend(['FRAGMENT_SPLIT','INIT'])
    features.append('feature liga { lookup BRACKET_TOKENIZE; lookup TOKENIZE_AROMATIC; lookup TOKENIZE; lookup INIT; lookup END; } liga;')
    features.append('feature calt { lookup LAYOUT_SELECT; } calt;')
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder(list(glyphs))
    builder.setupCharacterMap({ord(c): name for c,name in chars.items()})
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics(metrics)
    builder.setupHorizontalHeader(ascent=HEIGHT, descent=-100)
    builder.setupNameTable({'familyName': 'SMILES Diagrams', 'styleName': 'Regular',
                           'fullName': 'SMILES Diagrams Regular', 'psName': 'SMILESDiagrams-Regular'})
    # Retain Roboto's legal records for the copied source and atom labels.
    for name_id in (0,7,13,14):
        value = base['name'].getDebugName(name_id)
        if value:
            builder.font['name'].setName(value,name_id,3,1,0x409)
    builder.setupOS2(sTypoAscender=HEIGHT,sTypoDescender=-100,usWinAscent=HEIGHT,usWinDescent=100,fsType=0)
    builder.setupPost()
    builder.setupMaxp()
    builder.setupCOLR(colors, version=0)
    builder.setupCPAL([[tuple(int(c[i:i+2],16)/255 for i in (0,2,4))+(1.0,) for c in PALETTE]])
    font = builder.font
    font._decoder_base_digest = base._decoder_base_digest
    compiler = Builder(font, StringIO('\n'.join(features)))
    compiler.build()
    table = font['GSUB'].table
    for context_name,names,rules,*options in manual_contexts:
        backwards = bool(options and options[0])
        context = otTables.ChainContextSubst()
        context.Format = 2
        context.Coverage = buildCoverage(names,font.getReverseGlyphMap())
        for attribute,mapping in (
            ('BacktrackClassDef',{flag:i+1 for i,(flag,_) in enumerate(rules)} if backwards else {}),
            ('InputClassDef',{name:1 for name in names}),
            ('LookAheadClassDef',{} if backwards else {flag:i+1 for i,(flag,_) in enumerate(rules)}),
        ):
            definition = otTables.ClassDef()
            definition.classDefs = mapping
            setattr(context,attribute,definition)
        ruleset = otTables.ChainSubClassSet()
        ruleset.ChainSubClassRule = []
        for i,(_,target) in enumerate(rules):
            rule = otTables.ChainSubClassRule()
            rule.BacktrackGlyphCount,rule.Backtrack = (1,[i+1]) if backwards else (0,[])
            rule.InputGlyphCount,rule.Input = 1,[]
            rule.LookAheadGlyphCount,rule.LookAhead = (0,[]) if backwards else (1,[i+1])
            record = otTables.SubstLookupRecord()
            record.SequenceIndex,record.LookupListIndex = 0,compiler.named_lookups_[target].lookup_index
            rule.SubstCount,rule.SubstLookupRecord = 1,[record]
            ruleset.ChainSubClassRule.append(rule)
        ruleset.ChainSubClassRuleCount = len(rules)
        context.ChainSubClassSetCount,context.ChainSubClassSet = 2,[None,ruleset]
        index = compiler.named_lookups_[context_name].lookup_index
        old = table.LookupList.Lookup[index]
        table.LookupList.Lookup[index] = buildLookup([context],flags=old.LookupFlag,
            markFilterSet=old.MarkFilteringSet,table='GSUB',extension=True)
    atom_mapping = {tuple(rule.split()[1:3]): rule.split()[4].rstrip(';') for rule in atom_rules}
    atom_subtables = []
    firsts = list(dict.fromkeys(pair[0] for pair in atom_mapping))
    for start in range(0,len(firsts),128):
        subset = set(firsts[start:start+128])
        atom_subtables.append(buildLigatureSubstSubtable({pair: value for pair,value in atom_mapping.items() if pair[0] in subset}))
    table.LookupList.Lookup[compiler.named_lookups_['ATOM'].lookup_index] = buildLookup(atom_subtables,flags=8,table='GSUB',extension=True)
    expansion_items = list(expansions.items())
    table.LookupList.Lookup[compiler.named_lookups_['EXPAND'].lookup_index] = buildLookup([
        buildMultipleSubstSubtable(dict(expansion_items[i:i+256]))
        for i in range(0,len(expansion_items),256)
    ],table='GSUB',extension=True)
    liga = next(r.Feature for r in table.FeatureList.FeatureRecord if r.FeatureTag == 'liga')
    begin = liga.LookupListIndex[:-1]
    wrappers = []
    # Build format-3 context wrappers directly. This avoids expanding the large
    # coverage into format-1 alternatives while the feature compiler optimizes.
    def lookup_coverage(lookup):
        result = set()
        for subtable in lookup.SubTable:
            subtable = getattr(subtable, 'ExtSubTable', subtable)
            if hasattr(subtable, 'mapping'):
                result.update(subtable.mapping)
            elif hasattr(subtable, 'ligatures'):
                result.update(subtable.ligatures)
            elif hasattr(subtable, 'InputCoverage'):
                result.update(subtable.InputCoverage[0].glyphs)
            elif hasattr(subtable, 'Coverage'):
                coverage = subtable.Coverage
                result.update((coverage[0] if isinstance(coverage, list) else coverage).glyphs)
            else:
                raise ValueError('Unsupported lookup coverage')
        return buildCoverage(result, font.getReverseGlyphMap())
    coverages = {name: lookup_coverage(table.LookupList.Lookup[compiler.named_lookups_[name].lookup_index])
                 for name in set(cycle + ['FRAGMENT_COUNT','END'] + render_cycle)}
    # Shapers execute lookups in numerical index order. The final END wrapper
    # must follow every clock wrapper, even though its shared data came first.
    for target in [name for _ in range(PASSES) for name in cycle] + ['FRAGMENT_COUNT','END']:
        context = otTables.ContextSubst()
        context.Format, context.GlyphCount = 3, 1
        context.Coverage = [coverages[target]]
        record = otTables.SubstLookupRecord()
        record.SequenceIndex = 0
        record.LookupListIndex = compiler.named_lookups_[target].lookup_index
        context.SubstLookupRecord, context.SubstCount = [record], 1
        wrappers.append(len(table.LookupList.Lookup))
        table.LookupList.Lookup.append(buildLookup([context], table='GSUB', extension=True))
    table.LookupList.LookupCount = len(table.LookupList.Lookup)
    liga.LookupListIndex = [*begin, *wrappers]
    liga.LookupCount = len(liga.LookupListIndex)
    rendering_indices = []
    for target in render_cycle:
        context = otTables.ContextSubst()
        context.Format, context.GlyphCount = 3, 1
        context.Coverage = [coverages[target]]
        record = otTables.SubstLookupRecord()
        record.SequenceIndex = 0
        record.LookupListIndex = compiler.named_lookups_[target].lookup_index
        context.SubstLookupRecord, context.SubstCount = [record], 1
        rendering_indices.append(len(table.LookupList.Lookup))
        table.LookupList.Lookup.append(buildLookup([context], table='GSUB', extension=True))
    table.LookupList.LookupCount = len(table.LookupList.Lookup)
    calt = next(r.Feature for r in table.FeatureList.FeatureRecord if r.FeatureTag == 'calt')
    calt.LookupListIndex, calt.LookupCount = rendering_indices, len(rendering_indices)
    from brackets import isolate_bracket_labels
    isolate_bracket_labels(font)
    from packing import compact_maps
    compact_maps(font)
    replace_font_names(font, {1:'SMILES Diagrams',2:'Regular',3:'SMILES Diagrams 1.0',
                             4:'SMILES Diagrams Regular',5:'Version 1.8',6:'SMILESDiagrams-Regular',
                             16:'SMILES Diagrams',17:'Regular'})
    compact_glyphs(font)
    compact_contours(font)
    mark_modified_font(font, 'SMILES diagrams', kind='molecular diagram')
    compact_contours(font, rounds=8, min_uses=4)
    font['head'].created = font['head'].modified = 3849984000
    font.recalcTimestamp = False
    output.parent.mkdir(parents=True, exist_ok=True)
    font.save(output)
    topology = [[[e.a[0],e.a[1],e.b[0],e.b[1],int(bool(e.ring))] for e in edges]
                for _,_,edges,_ in layouts]
    output.with_suffix('.topologies.json').write_text(json.dumps(topology,separators=(',',':'))+'\n')
    base.close()
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path(__file__).with_name('smiles-font.ttf'))
    args = parser.parse_args()
    print(build_font(args.output))


if __name__ == '__main__':
    main()
