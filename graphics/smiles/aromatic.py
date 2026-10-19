# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Compile aromatic endpoint recognition into the font's rendering stage."""


def compile_aromatic_bonds(add, marks, lookup, atoms, bonds, chemical_bond, point):
    implicit = {name:record for name,record in bonds.items() if record[2]==1}
    candidates, aromatic = {}, {}
    for name,(a,b,_,ring) in implicit.items():
        candidate = name+'_aromatic_start'
        marks.append(add(candidate,chemical_bond(point(*a),point(*b),1),color=0))
        target = f'bond_{a[0]}_{a[1]}_{b[0]}_{b[1]}_4_{ring}'
        marks.append(add(target,chemical_bond(point(*a),point(*b),4),color=0))
        bonds[target] = (a,b,4,ring)
        candidates[name],aromatic[name] = candidate,target
    cycle = []
    for index,node in enumerate(sorted({p for a,b,_,_ in implicit.values() for p in (a,b)})):
        incident, mapping = [], {}
        for name,(a,b,_,_) in implicit.items():
            if node not in (a,b):
                continue
            incident.extend((name,candidates[name],aromatic[name]))
            if node==a:
                mapping[name]=candidates[name]
            else:
                mapping[candidates[name]]=aromatic[name]
        atom_names = [name for (element,n,d),name in atoms.items() if (n,d)==node]
        lower = [name for (element,n,d),name in atoms.items() if (n,d)==node and element.islower()]
        # Include all clip-free implicit, candidate and aromatic variants so
        # other incident edges can be crossed without losing the atom anchor.
        rules = [f'sub {src} by {dst};' for src,dst in mapping.items()]
        mapping_name = f'AROMATIC_MAP_{index}'
        lookup(mapping_name,rules,'0')
        context_name = f'AROMATIC_NODE_{index}'
        edge_set = '['+' '.join(incident)+']'
        lower_set = '['+' '.join(lower)+']'
        rules = []
        for intervening in range(10):
            skipped = ' '.join([edge_set]*intervening)
            rules.extend([f'sub {lower_set} {skipped} {edge_set}\' lookup {mapping_name};',
                          f'sub {edge_set}\' lookup {mapping_name} {skipped} {lower_set};'])
        lookup(context_name,rules,'UseMarkFilteringSet ['+' '.join(incident+atom_names)+']')
        cycle.append(context_name)
    # Only one lowercase endpoint means an ordinary single bond, as in Cc1...
    lookup('AROMATIC_RESTORE',[f'sub {candidate} by {name};' for name,candidate in candidates.items()],'0')
    return cycle+['AROMATIC_RESTORE']


def ring_circles(edges, positions):
    """Return chordless ring faces with an inset circle inside each polygon."""
    import math
    adjacency = {n:set() for n in positions}
    edge_indices = {}
    for index,edge in enumerate(edges):
        a,b = edge.a[0],edge.b[0]
        adjacency[a].add(b)
        adjacency[b].add(a)
        edge_indices[frozenset((a,b))] = index
    cycles = set()
    def visit(start,path):
        for node in sorted(adjacency[path[-1]]):
            if node==start and len(path)>=3:
                cycle = tuple(path)
                cycles.add(min(cycle,(start,*reversed(path[1:]))))
            elif node>start and node not in path:
                visit(start,path+[node])
    for start in sorted(adjacency):
        visit(start,[start])
    result = []
    for cycle in sorted(cycles):
        size = len(cycle)
        if any(cycle[j] in adjacency[cycle[i]] for i in range(size)
               for j in range(i+1,size) if j-i not in (1,size-1)):
            continue
        center = tuple(sum(positions[n][axis] for n in cycle)/size for axis in (0,1))
        indices,clearance = set(),float('inf')
        for i,a in enumerate(cycle):
            b = cycle[(i+1)%size]
            indices.add(edge_indices[frozenset((a,b))])
            p,q = positions[a],positions[b]
            clearance = min(clearance,abs((q[0]-p[0])*(center[1]-p[1])-
                                           (q[1]-p[1])*(center[0]-p[0]))/math.dist(p,q))
        result.append((indices,center,clearance*.68))
    return result


def circle_glyph(center, radius, thickness=7):
    """An annulus with opposing contour winding for monochrome and COLR."""
    import math
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    pen = TTGlyphPen(None)
    for r,direction in ((radius+thickness/2,1),(radius-thickness/2,-1)):
        step = direction*math.pi/4
        pen.moveTo((center[0]+r,center[1]))
        for i in range(8):
            control = (i+.5)*step
            end = (i+1)*step
            pen.qCurveTo((center[0]+r/math.cos(step/2)*math.cos(control),
                          center[1]+r/math.cos(step/2)*math.sin(control)),
                         (center[0]+r*math.cos(end),center[1]+r*math.sin(end)))
        pen.closePath()
    return pen.glyph()


def compile_ring_circles(add, marks, lookup, layouts, flags, bonds, width):
    """Emit circles for fully aromatic faces, preserving other bond orders."""
    rules,expansions,reset,cache = [],{},[],{}
    maximum = 0
    for index,(_,_,edges,positions) in enumerate(layouts):
        circles = ring_circles(edges,positions)
        if not circles:
            continue
        maximum = max(maximum,len(circles))
        states = {0:flags[index]}
        for mask in range(1,1<<len(circles)):
            states[mask] = add(f'circle_state_{index}_{mask}',advance=width)
            reset.append(f'sub {states[mask]} by {flags[index]};')
        for face,(required,center,radius) in enumerate(circles):
            key = (*[round(v,3) for v in center],round(radius,3))
            if key not in cache:
                name = add(f'aromatic_circle_{len(cache)}',circle_glyph(center,radius),color=0)
                marks.append(name)
                cache[key]=name
            classes = []
            for edge_index,edge in enumerate(edges):
                orders = (4,) if edge_index in required else (1,2,3,4,5)
                names = [edge.name(order,digit) for order in orders
                         for digit in ((1,2,3) if edge.ring else (0,))]
                classes.append('['+' '.join(n for n in names if n in bonds)+']')
            for mask,state in states.items():
                if mask&(1<<face):
                    continue
                token = add(f'circle_emit_{index}_{face}_{mask}')
                rules.append(f"sub origin {' '.join(classes)} {state}' by {token};")
                expansions[token] = (cache[key],states[mask|(1<<face)])
    lookup('CIRCLE_FIND',rules,'UseMarkFilteringSet [origin '+' '.join(bonds)+']')
    lookup('CIRCLE_EXPAND',[f'sub {token} by {circle} {state};'
                            for token,(circle,state) in expansions.items()],'0')
    lookup('CIRCLE_RESET',reset,'0')
    return [name for _ in range(maximum) for name in ('CIRCLE_FIND','CIRCLE_EXPAND')]+['CIRCLE_RESET']
