# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Bounded bracket atom lexing and native mark attachment for atom labels."""
import math

DIRECTIONS = {'R':(1,0), 'L':(-1,0), 'U':(0,1), 'D':(0,-1)}


def bond_overlap(bounds, vector, padding=12.5):
    """Length of an incident bond inside a padded decoration rectangle."""
    enter,leave = 0.0,1.0
    for low,high,component in zip(bounds[:2],bounds[2:],vector):
        low,high = low-padding,high+padding
        if abs(component)<1e-9:
            if not low<=0<=high:
                return 0
        else:
            a,b = sorted((low/component,high/component))
            enter,leave = max(enter,a),min(leave,b)
            if enter>=leave:
                return 0
    return (leave-enter)*math.hypot(*vector)


def label_direction(node, edges, positions):
    """Put explicit hydrogen on the side with the most room between bonds."""
    x,y = positions[node]
    neighbors = [e.b[0] if e.a[0]==node else e.a[0]
                 for e in edges if node in (e.a[0],e.b[0])]
    vectors = [(positions[n][0]-x,positions[n][1]-y) for n in neighbors]
    return min(DIRECTIONS, key=lambda key: max(
        ((dx*DIRECTIONS[key][0]+dy*DIRECTIONS[key][1])/math.hypot(dx,dy)
         for dx,dy in vectors), default=-1))


class BracketAtoms:
    def __init__(self, add, marks, chars, metrics, glyphs, draw_text, elements, aromatic):
        from fontTools.pens.ttGlyphPen import TTGlyphPen
        self.add, self.marks = add, marks
        self.flags, self.tokens, self.labels, self.anchors = {}, {}, {}, {}
        self.decorations, self.profiles, self.anchor_vectors = {}, {}, {}
        self.lexical = []
        self.node_anchors = {}
        for element in (*elements,*aromatic):
            self.flags[element] = add('bracket_input_'+element)
            marks.append(self.flags[element])
            for hydrogens in range(5):
                for charge in range(-3,4):
                    key = element,hydrogens,charge
                    stem = f'{element}_{hydrogens}_{charge+3}'
                    for direction in DIRECTIONS:
                        outline,boxes = draw_text(element,hydrogens,charge,direction)
                        name = add(f'bracket_label_{stem}_{direction}',
                                   outline,
                                   color={'N':1,'O':2,'P':3,'S':3,'F':4,'Cl':4,'Br':3,'I':5}.get(element.upper() if element.islower() else element,0))
                        marks.append(name)
                        self.labels[key,direction]=name
                        self.decorations[key,direction]=boxes
                    canonical = '['+element+('H'+(str(hydrogens) if hydrogens>1 else '') if hydrogens else '')+(('+' if charge>0 else '-')+(str(abs(charge)) if abs(charge)>1 else '') if charge else '')+']'
                    pen,advance = TTGlyphPen(glyphs),0
                    for char in canonical:
                        pen.addComponent(chars[char],(1,0,0,1,advance,0))
                        advance += metrics[chars[char]][0]
                    token = add('bracket_token_'+stem,pen.glyph(),advance)
                    self.tokens[key]=token
                    hs = ['','H0'] if not hydrogens else ['H','H1'] if hydrogens==1 else ['H'+str(hydrogens)]
                    qs = [''] if not charge else list(dict.fromkeys((('+' if charge>0 else '-')+str(abs(charge)),('+' if charge>0 else '-')*abs(charge))))
                    for h in hs:
                        for q in qs:
                            source = '['+element+h+q+']'
                            self.lexical.append(f'sub {" ".join(chars[c] for c in source)} by {token};')

    @staticmethod
    def charge_text(charge):
        return (str(abs(charge)) if abs(charge)>1 else '')+('+' if charge>0 else '-') if charge else ''

    def parser_lookups(self, lookup, inputs, initial, states, atoms, state, hidden):
        lookup('BRACKET_TOKENIZE',self.lexical,'0')
        lookup('BRACKET_EXPAND',[
            f'sub {token} by {inputs[e.upper() if e.islower() else e]} {self.flags[e]} {self.labels[(e,h,q),"R"]};'
            for (e,h,q),token in self.tokens.items()
        ],'0')
        lookup('BRACKET_START',[
            f"sub [{' '.join([initial,*states])}] [{' '.join(self.tokens.values())}]' lookup BRACKET_EXPAND;"
        ])
        filters = 'UseMarkFilteringSet ['+' '.join([*atoms.values(),*self.flags.values()])+']'
        rules=[]
        for e,flag in self.flags.items():
            name = 'BRACKET_LABEL_MAP_'+e
            lookup(name,[f"sub {atoms[e.upper() if e.islower() else e,n,d]} by {atoms['['+e+']',n,d]};"
                         for n in range(10) for d in range(3)],'0')
            rules.extend(f"sub {atoms[e.upper() if e.islower() else e,n,d]}' lookup {name} {state(n+1,n,d)} {flag};"
                         for n in range(10) for d in range(3))
        lookup('BRACKET_LABEL',rules,filters)
        # Parser states advance past existing marks. Keep an atom-indexed
        # anchor beside each label on that tape, rather than attaching to the
        # nearest chemical atom after the state has moved to the end.
        anchor_rules=[]
        for n in range(10):
            for d in range(3):
                marker = self.add(f'bracket_node_{n}_{d}')
                self.marks.append(marker)
                self.node_anchors[n,d] = marker
                self.anchor(marker,(110+n*165,790-d*300+(n%2)*95),'L' if n==0 else 'U' if n%2 else 'D')
                mapping = f'BRACKET_NODE_MAP_{n}_{d}'
                lookup(mapping,[f'sub {flag} by {marker};' for flag in self.flags.values()],'0')
                anchor_rules.append(f"sub {state(n+1,n,d)} [{' '.join(self.flags.values())}]' lookup {mapping};")
        lookup('BRACKET_FLAG_EAT',anchor_rules,
               'UseMarkFilteringSet ['+' '.join(self.flags.values())+']')

    def anchor(self, name, position, direction='R'):
        self.anchors[name] = (position,direction)
        return name

    def positioned_anchor(self, position, direction, vectors):
        vectors = tuple(sorted(vectors))
        profile = self.profiles.setdefault(vectors,len(self.profiles))
        name = f'bracket_anchor_{direction}_{position[0]}_{position[1]}_{profile}'
        if name not in self.anchors:
            self.marks.append(self.add(name))
            self.anchor(name,position,direction)
            self.anchor_vectors[name]=vectors
        return name

    def rendering(self, lookup, features, width, manual_contexts):
        cycle=[]
        filters = 'UseMarkFilteringSet ['+' '.join([*self.anchors,*self.labels.values()])+']'
        # Select among shared label outlines using the full H/count/charge
        # bounds and local bonds. This is compiled into GSUB; the application
        # still supplies only the original SMILES text.
        choices,groups,cache = {},{},{}
        for anchor,(_,preferred) in self.anchors.items():
            vectors = self.anchor_vectors.get(anchor,())
            profile = vectors,preferred
            if profile not in cache:
                selected=[]
                for key in self.tokens:
                    direction = min(DIRECTIONS,key=lambda d:(
                        sum(bond_overlap(box,v) for box in self.decorations[key,d] for v in vectors),
                        d!=preferred,
                    ))
                    # Reuse R for identical decorations (notably neutral
                    # atoms without H). Avoid unnecessary orientation maps
                    # in the already large native substitution table.
                    if self.decorations[key,direction]==self.decorations[key,'R']:
                        direction='R'
                    selected.append(direction)
                cache[profile]=tuple(selected)
            selected=cache[profile]
            if all(d=='R' for d in selected):
                continue
            if selected not in choices:
                mapping='BRACKET_ORIENT_MAP_'+str(len(choices))
                lookup(mapping,[f'sub {self.labels[key,"R"]} by {self.labels[key,d]};'
                                for key,d in zip(self.tokens,selected) if d!='R'],'0')
                choices[selected]=mapping
            groups.setdefault(selected,[]).append(anchor)
        rules=[(anchor,choices[selected]) for selected,anchors in groups.items() for anchor in anchors]
        labels=[self.labels[key,'R'] for key in self.tokens]
        anchor,target=rules[0]
        lookup('BRACKET_ORIENT',[f"sub {anchor} [{' '.join(labels)}]' lookup {target};"],filters)
        # A shared format-2 context avoids repeating the full label coverage
        # for every bond profile, which would overflow 16-bit table offsets.
        manual_contexts.append(('BRACKET_ORIENT',labels,rules,True))
        cycle.append('BRACKET_ORIENT')
        for name in self.labels.values():
            features.append(f'markClass {name} <anchor 0 0> @BRACKET_LABELS;')
        features.append('lookup BRACKET_ATTACH useExtension { lookupflag '+filters+';')
        # These marks follow the canvas-advance glyph. Subtract its width
        # so attachment remains relative to this diagram's original pen.
        for name,(position,_) in self.anchors.items():
            features.append(f'pos mark {name} <anchor {position[0]-width} {position[1]}> mark @BRACKET_LABELS;')
        features.append('} BRACKET_ATTACH;')
        features.append('feature mkmk { lookup BRACKET_ATTACH; } mkmk;')
        return cycle


def isolate_bracket_labels(font):
    """Use conventional element–hydrogen order for a standalone bracket atom."""
    from fontTools.otlLib.builder import buildCoverage,buildLookup,buildSingleSubstSubtable
    from fontTools.ttLib.tables import otTables
    table = font['GSUB'].table
    glyphs = font.getReverseGlyphMap()
    mapping = {name:name[:-1]+'R' for name in glyphs
               if name.startswith('bracket_label_') and name.endswith('_L')}
    target = len(table.LookupList.Lookup)
    table.LookupList.Lookup.append(buildLookup([buildSingleSubstSubtable(mapping)],table='GSUB',extension=True))
    context = otTables.ChainContextSubst()
    context.Format = 3
    context.BacktrackCoverage = [buildCoverage(names,glyphs) for names in (
        ['bracket_node_0_0'],['end'],
        [name for name in glyphs if name.startswith('atom_bracket_') and name.endswith('_0_0')],['origin'])]
    context.BacktrackGlyphCount = len(context.BacktrackCoverage)
    context.InputCoverage,context.InputGlyphCount = [buildCoverage(mapping,glyphs)],1
    context.LookAheadCoverage,context.LookAheadGlyphCount = [],0
    record = otTables.SubstLookupRecord()
    record.SequenceIndex,record.LookupListIndex = 0,target
    context.SubstLookupRecord,context.SubstCount = [record],1
    index = len(table.LookupList.Lookup)
    table.LookupList.Lookup.append(buildLookup([context],table='GSUB',extension=True))
    table.LookupList.LookupCount = len(table.LookupList.Lookup)
    feature = next(r.Feature for r in table.FeatureList.FeatureRecord if r.FeatureTag=='calt')
    feature.LookupListIndex.append(index)
    feature.LookupCount = len(feature.LookupListIndex)
