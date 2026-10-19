# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Compile scaffold selection, skeletal bonds and label placement into GSUB."""
from collections import defaultdict, deque

from layout import scaffolds


def ring_side(edge, edges, positions):
    """Inward normal for the smaller cycle containing this edge, if any."""
    adjacency = defaultdict(list)
    for other in edges:
        if other == edge:
            continue
        a,b = other.a[0],other.b[0]
        adjacency[a].append(b)
        adjacency[b].append(a)
    a,b = edge.a[0],edge.b[0]
    queue, path = deque([(a,[a])]), None
    while queue:
        current, visited = queue.popleft()
        if current == b:
            path = visited
            break
        for neighbor in adjacency[current]:
            if neighbor not in visited:
                queue.append((neighbor,visited+[neighbor]))
    if path is None:
        return 0
    cx = sum(positions[n][0] for n in path)/len(path)
    cy = sum(positions[n][1] for n in path)/len(path)
    p,q = positions[a],positions[b]
    return 1 if (q[0]-p[0])*(cy-p[1])-(q[1]-p[1])*(cx-p[0]) > 0 else -1


def compile_rendering(add, marks, features, lookup, atoms, bond_records,
                      label_glyph, chemical_bond, base_point, width, brackets):
    layouts = scaffolds()
    base_bonds = dict(bond_records)
    from aromatic import compile_aromatic_bonds
    aromatic_cycle = compile_aromatic_bonds(add,marks,lookup,atoms,base_bonds,chemical_bond,base_point)
    # Complete graph recognition sees bond order classes, while element labels
    # and completed parser marks are skipped. Elements remain freely editable.
    features.append('@ORIGINAL_BONDS = ['+' '.join(base_bonds)+'];')
    end_rules, layout_flags = [], []
    for index, (_, vertices, edges, positions) in enumerate(layouts):
        flag = add(f'layout_{index}',advance=width)
        layout_flags.append(flag)
        classes = []
        for edge in edges:
            names = [edge.name(order,digit) for order in (1,2,3,4,5)
                     for digit in ((1,2,3) if edge.ring else (0,))]
            classes.append('['+' '.join(n for n in names if n in base_bonds)+']')
        end_rules.append(f'sub origin {" ".join(classes)} end\' by {flag};')
    lookup('LAYOUT_SELECT',end_rules,'UseMarkFilteringSet [origin @ORIGINAL_BONDS]')
    original_atoms = list(atoms.values())
    marks.append(add('isolated_carbon',label_glyph('C',base_point(0,0),True),color=0))
    lookup('ISOLATED_C',["sub origin atom_C_0_0' end by isolated_carbon;"],
           'UseMarkFilteringSet [origin '+' '.join(original_atoms)+']')
    invalid = add('unsupported_ring',label_glyph('X',(110,1400)),advance=width)
    ring_bonds = [name for name,record in base_bonds.items() if record[3]]
    lookup('UNSUPPORTED_RING',[f"sub [{' '.join(ring_bonds)}] end' by {invalid};"],
           'UseMarkFilteringSet ['+' '.join(ring_bonds)+']')
    render_cycle = [*aromatic_cycle,'ISOLATED_C','LAYOUT_SELECT','UNSUPPORTED_RING']
    from aromatic import compile_ring_circles
    render_cycle.extend(compile_ring_circles(add,marks,lookup,layouts,layout_flags,base_bonds,width))
    # Clip only at explicit atom labels. Carbon endpoints meet at bare vertices.
    # Clip before geometry selection so each edge retains its parser identity.
    variants, pairs = {}, defaultdict(list)
    for name,(a,b,order,ring) in base_bonds.items():
        for ca in (0,1):
            for cb in (0,1):
                variant = name if not (ca or cb) else f'{name}_clip{ca}{cb}'
                if ca or cb:
                    marks.append(add(variant,chemical_bond(base_point(*a),base_point(*b),order,ca,cb),color=0))
                variants[name,ca,cb] = variant
                pairs[a,b].append(variant)
    for node_index,node in enumerate(sorted({node for pair in pairs for node in pair})):
        incident = [name for (a,b),names in pairs.items() if node in (a,b) for name in names]
        hetero = [name for (element,n,d),name in atoms.items() if (n,d)==node and element.upper()!='C']
        atom_names = [name for (element,n,d),name in atoms.items() if (n,d)==node]
        edge_class = f'@INCIDENT_{node_index}'
        features.append(edge_class+' = ['+' '.join(incident)+'];')
        mapping = {}
        for name,(a,b,order,ring) in base_bonds.items():
            if node not in (a,b):
                continue
            for ca in (0,1):
                for cb in (0,1):
                    src = variants[name,ca,cb]
                    dst = variants[name,1 if node==a else ca,1 if node==b else cb]
                    if src != dst:
                        mapping[src]=dst
        map_name = f'CLIP_MAP_{node_index}'
        lookup(map_name,[f'sub {src} by {dst};' for src,dst in mapping.items()],'0')
        rules = []
        for intervening in range(10):
            skipped = ' '.join([edge_class]*intervening)
            rules.extend([f'sub [{" ".join(hetero)}] {skipped} {edge_class}\' lookup {map_name};',
                          f'sub {edge_class}\' lookup {map_name} {skipped} [{" ".join(hetero)}];'])
        context = f'CLIP_{node_index}'
        lookup(context,rules,f'UseMarkFilteringSet [{edge_class} {" ".join(atom_names)}]')
        render_cycle.append(context)
    # Cache pure geometric outlines across scaffolds. The font selects a
    # scaffold by connectivity, not an exact SMILES string or molecule name.
    geometry_cache, label_cache = {}, {}
    manual_contexts = []
    pair_maps, atom_maps = defaultdict(list), defaultdict(list)
    for index, (_, vertices, edges, positions) in enumerate(layouts):
        mapping = {}
        for edge in edges:
            a,b = positions[edge.a[0]],positions[edge.b[0]]
            inward = ring_side(edge,edges,positions)
            for order in (1,2,3,4,5):
                for ca in (0,1):
                    for cb in (0,1):
                        key = (a,b,1 if order in (4,5) else order,ca,cb,inward if order==2 else 0)
                        if key not in geometry_cache:
                            glyph = add(f'chemical_bond_{len(geometry_cache)}',
                                        chemical_bond(a,b,order,ca,cb,inward),color=0)
                            marks.append(glyph)
                            geometry_cache[key]=glyph
                        for digit in ((1,2,3) if edge.ring else (0,)):
                            src = variants.get((edge.name(order,digit),ca,cb))
                            if src:
                                mapping[src]=geometry_cache[key]
            pair_maps[edge.a,edge.b].append(index)
        map_name = f'GEOMETRY_MAP_{index}'
        lookup(map_name,[f'sub {src} by {dst};' for src,dst in mapping.items()],'0')
        mapping = {}
        for n,d in vertices:
            for (element,nn,dd),src in atoms.items():
                if (nn,dd)!=(n,d) or element.upper()=='C':
                    continue
                if element.startswith('['):
                    from brackets import label_direction
                    x,y=positions[n]
                    vectors=[(positions[other][0]-x,positions[other][1]-y)
                             for e in edges if n in (e.a[0],e.b[0])
                             for other in [e.b[0] if e.a[0]==n else e.a[0]]]
                    mapping[brackets.node_anchors[n,d]] = brackets.positioned_anchor(
                        positions[n],label_direction(n,edges,positions),vectors)
                    continue
                label_element = element.upper() if element.islower() else element
                key = (label_element,positions[n])
                if key not in label_cache:
                    name = f'chemical_label_{label_element}_{positions[n][0]}_{positions[n][1]}'
                    marks.append(add(name,label_glyph(element,positions[n]),color={'N':1,'O':2,'P':3,'S':3,'F':4,'Cl':4,'Br':3,'I':5}.get(label_element,0)))
                    label_cache[key]=name
                mapping[src]=label_cache[key]
            atom_maps[n,d].append(index)
        lookup(f'LABEL_MAP_{index}',[f'sub {src} by {dst};' for src,dst in mapping.items()],'0')
    for pair_index,(pair,indices) in enumerate(pair_maps.items()):
        names = pairs[pair]
        context = f'GEOMETRY_{pair_index}'
        lookup(context,[f'sub [{" ".join(names)}]\' lookup GEOMETRY_MAP_{i} {layout_flags[i]};'
                        for i in indices[:1]],'UseMarkFilteringSet ['+' '.join(names)+']')
        manual_contexts.append((context,names,[(layout_flags[i],f'GEOMETRY_MAP_{i}') for i in indices]))
        render_cycle.append(context)
    for atom_index,(node,indices) in enumerate(atom_maps.items()):
        names = [name for (e,n,d),name in atoms.items() if (n,d)==node and e.upper()!='C' and not e.startswith('[')]
        context = f'LABEL_{atom_index}'
        lookup(context,[f'sub [{" ".join(names)}]\' lookup LABEL_MAP_{i} {layout_flags[i]};'
                        for i in indices[:1]],'UseMarkFilteringSet ['+' '.join(names)+']')
        manual_contexts.append((context,names,[(layout_flags[i],f'LABEL_MAP_{i}') for i in indices]))
        render_cycle.append(context)
    # Bracket label anchors trail the completed parser state, so their
    # scaffold selector is behind them, rather than ahead of atom drawings.
    for atom_index,(node,indices) in enumerate(atom_maps.items()):
        marker = brackets.node_anchors[node]
        context = f'BRACKET_POSITION_{atom_index}'
        lookup(context,[f"sub {layout_flags[i]} {marker}' lookup LABEL_MAP_{i};" for i in indices[:1]],
               f'UseMarkFilteringSet [{marker}]')
        manual_contexts.append((context,[marker],[(layout_flags[i],f'LABEL_MAP_{i}') for i in indices],True))
        render_cycle.append(context)
    render_cycle.extend(brackets.rendering(lookup,features,width,manual_contexts))
    from joins import compile_ring_joins
    render_cycle.extend(compile_ring_joins(add,marks,features,lookup,layouts,layout_flags,
                                         geometry_cache,chemical_bond,ring_side))
    return render_cycle, layouts, manual_contexts
