# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Continuous polygon outlines for unlabeled, simple carbon rings."""
import math
from fontTools.pens.ttGlyphPen import TTGlyphPen


def simple_ring(vertices, edges, positions):
    if len(vertices)!=len(edges):
        return None
    adjacency = {n:[] for n,d in vertices}
    for edge in edges:
        a,b=edge.a[0],edge.b[0]
        adjacency[a].append(b)
        adjacency[b].append(a)
    if any(len(neighbors)!=2 for neighbors in adjacency.values()):
        return None
    start=min(adjacency)
    ordered=[start]
    previous,current=start,min(adjacency[start])
    while current!=start:
        if current in ordered:
            return None
        ordered.append(current)
        previous,current=current,next(n for n in adjacency[current] if n!=previous)
    return [positions[n] for n in ordered] if len(ordered)==len(vertices) else None


def polygon_band(points, thickness=9):
    """One hollow contour pair, with true miter joins at every vertex."""
    area=sum(p[0]*q[1]-p[1]*q[0] for p,q in zip(points,points[1:]+points[:1]))
    winding=1 if area>0 else -1
    normals=[]
    for p,q in zip(points,points[1:]+points[:1]):
        dx,dy=q[0]-p[0],q[1]-p[1]
        length=math.hypot(dx,dy)
        normals.append((winding*dy/length,-winding*dx/length))
    outer,inner=[],[]
    for i,(x,y) in enumerate(points):
        a,b=normals[i-1],normals[i]
        scale=thickness/2/(1+a[0]*b[0]+a[1]*b[1])
        dx,dy=(a[0]+b[0])*scale,(a[1]+b[1])*scale
        outer.append((x+dx,y+dy))
        inner.append((x-dx,y-dy))
    pen=TTGlyphPen(None)
    for contour in (outer,list(reversed(inner))):
        pen.moveTo(contour[0])
        for point in contour[1:]:
            pen.lineTo(point)
        pen.closePath()
    return pen.glyph()


def compile_ring_joins(add, marks, features, lookup, layouts, flags,
                       geometry, chemical_bond, ring_side):
    selections,expansions,mapping={},[],{}
    for index,(_,vertices,edges,positions) in enumerate(layouts):
        points=simple_ring(vertices,edges,positions)
        if points is None:
            continue
        outline=add(f'joined_ring_{index}',polygon_band(points),color=0)
        marks.append(outline)
        flag=add(f'joined_ring_state_{index}')
        classes=[]
        for edge in edges:
            a,b=positions[edge.a[0]],positions[edge.b[0]]
            inward=ring_side(edge,edges,positions)
            single=geometry[a,b,1,0,0,0]
            double=geometry[a,b,2,0,0,inward]
            classes.append('['+single+' '+double+']')
            mapping[single]='hidden'
            if double not in mapping:
                inner=add(f'ring_inner_{len(mapping)}',chemical_bond(a,b,2,0,0,inward,inner_only=True),color=0)
                marks.append(inner)
                mapping[double]=inner
        selections[flag]=f"sub origin {' '.join(classes)} {flags[index]}' by {flag};"
        expansions.append(f'sub {flag} by {outline} {flags[index]};')
    features.append('@JOIN_BONDS = ['+' '.join(mapping)+'];')
    features.append('@JOIN_FLAGS = ['+' '.join(selections)+'];')
    lookup('RING_JOIN_SELECT',list(selections.values()),'UseMarkFilteringSet [origin @JOIN_BONDS]')
    lookup('RING_JOIN_MAP',[f'sub {src} by {dst};' for src,dst in mapping.items()],'0')
    lookup('RING_JOIN_CLEAN',[
        "sub @JOIN_BONDS' lookup RING_JOIN_MAP "+' '.join(['@JOIN_BONDS']*n)+' @JOIN_FLAGS;'
        for n in range(10)
    ],'UseMarkFilteringSet [@JOIN_BONDS]')
    lookup('RING_JOIN_EXPAND',expansions,'0')
    return ['RING_JOIN_SELECT','RING_JOIN_CLEAN','RING_JOIN_EXPAND']
