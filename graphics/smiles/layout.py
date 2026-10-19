# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Original geometric scaffolds selected by the font from its shaped graph.

Scaffolds describe connectivity, never a particular molecule or element list.
No layout code runs in the playground.
"""
from dataclasses import dataclass
import math
import re

LENGTH = 190


@dataclass(frozen=True)
class Edge:
    a: tuple
    b: tuple
    ring: int
    event: int

    def name(self, order=1, digit=None):
        return f'bond_{self.a[0]}_{self.a[1]}_{self.b[0]}_{self.b[1]}_{order}_{self.ring if digit is None else digit}'


def graph(source):
    """Describe the interpreter's output order for an all-carbon scaffold."""
    atoms, edges, stack, rings = [], [], [], {}
    current, depth = None, 0
    for event, token in enumerate(re.findall(r'Cl|Br|[A-Z]|[123()]', source)):
        if token[0].isalpha():
            destination = (len(atoms), depth)
            atoms.append(destination)
            if current is not None:
                edges.append(Edge(current, destination, 0, event))
            current = destination
        elif token == '(':
            stack.append(current)
            depth += 1
        elif token == ')':
            current = stack.pop()
            depth -= 1
        elif token in rings:
            origin, opened = rings.pop(token)
            edges.append(Edge(origin, current, int(token), opened))
        else:
            rings[token] = (current, event)
    return atoms, sorted(edges, key=lambda e:e.event)


def regular(size, center=(500,500), angle=math.pi):
    radius = LENGTH / (2*math.sin(math.pi/size))
    return [(center[0]+radius*math.cos(angle-i*2*math.pi/size),
             center[1]+radius*math.sin(angle-i*2*math.pi/size)) for i in range(size)]


def extend(origin, angle, count):
    result, x, y = [], *origin
    for i in range(count):
        direction = angle + (0 if i % 2 == 0 else math.pi/3)
        x += LENGTH*math.cos(direction)
        y += LENGTH*math.sin(direction)
        result.append((x,y))
    return result


def cycle(size, prefix=0, suffix=0, branch=None, branch_length=1):
    points, source, slot = {}, 'C'*prefix, prefix
    vertices = regular(size)
    for i in range(prefix):
        points[i] = extend(vertices[0], math.pi, prefix)[prefix-1-i]
    for i in range(size):
        source += 'C' + ('1' if i == 0 else '')
        points[slot], slot = vertices[i], slot+1
        if i == branch:
            source += '('+'C'*branch_length+')'
            angle = math.atan2(vertices[i][1]-500, vertices[i][0]-500)
            for p in extend(vertices[i],angle,branch_length):
                points[slot], slot = p, slot+1
    source += '1'+'C'*suffix
    angle = math.atan2(vertices[-1][1]-500, vertices[-1][0]-500)
    for p in extend(vertices[-1],angle,suffix):
        points[slot], slot = p, slot+1
    return source, points


def connected(first, second):
    vertices = regular(first)
    anchor = vertices[-1]
    angle = math.atan2(anchor[1]-500, anchor[0]-500)
    radius = LENGTH/(2*math.sin(math.pi/second))
    center = (anchor[0]+(LENGTH+radius)*math.cos(angle),
              anchor[1]+(LENGTH+radius)*math.sin(angle))
    other = regular(second,center,angle+math.pi)
    source = 'C1'+'C'*(first-1)+'1C1'+'C'*(second-1)+'1'
    return source, dict(enumerate(vertices+other))


def fused(first, second):
    vertices = regular(first)
    a,b = vertices[0],vertices[-1]
    middle = ((a[0]+b[0])/2,(a[1]+b[1])/2)
    dx,dy = b[0]-a[0],b[1]-a[1]
    normal = (-dy/LENGTH, dx/LENGTH)
    if normal[0]*(500-middle[0])+normal[1]*(500-middle[1]) > 0:
        normal = (-normal[0],-normal[1])
    distance = LENGTH/(2*math.tan(math.pi/second))
    center = (middle[0]+normal[0]*distance,middle[1]+normal[1]*distance)
    alpha = math.atan2(a[1]-center[1],a[0]-center[0])
    beta = math.atan2(b[1]-center[1],b[0]-center[0])
    turn = (beta-alpha+math.pi)%(2*math.pi)-math.pi
    radius = LENGTH/(2*math.sin(math.pi/second))
    for i in range(1,second-1):
        angle = beta+i*turn
        vertices.append((center[0]+radius*math.cos(angle),center[1]+radius*math.sin(angle)))
    source = 'C12'+'C'*(first-2)+'C1'+'C'*(second-2)+'2'
    return source, dict(enumerate(vertices))


def spiro(first, second):
    vertices = regular(first)
    radius = LENGTH/(2*math.sin(math.pi/second))
    center = (vertices[0][0]-radius,vertices[0][1])
    other = regular(second,center,0)
    source = 'C12('+'C'*(first-1)+'1)'+'C'*(second-1)+'2'
    return source, dict(enumerate(vertices+other[1:]))


def scaffolds():
    candidates = []
    for size in range(3,11):
        for prefix in range(11-size):
            for suffix in range(11-size-prefix):
                candidates.append(cycle(size,prefix,suffix))
        for branch in range(size):
            for length in range(1,11-size):
                candidates.append(cycle(size,branch=branch,branch_length=length))
    for first in range(3,8):
        for second in range(3,8):
            if first+second <= 10:
                candidates.append(connected(first,second))
            if first+second-2 <= 10:
                candidates.append(fused(first,second))
            if first+second-1 <= 10:
                candidates.append(spiro(first,second))
    # Common acyclic branch scaffolds keep bond lengths and 120-degree
    # junctions consistent, independently of the chosen atom labels.
    for length in range(2,10):
        for branch in range(length):
            points,source,slot = {},'',0
            for i in range(length):
                p = (110+i*LENGTH*math.cos(math.pi/6),400+(i%2)*LENGTH/2)
                source += 'C'
                points[slot],slot = p,slot+1
                if i==branch:
                    source += '(C)'
                    points[slot],slot = (p[0],p[1]+(LENGTH if i%2 else -LENGTH)),slot+1
            candidates.append((source,points))
    candidates.append(('CC(C(C)C)C', {0:(110,400),1:(275,495),2:(275,685),
                                              3:(110,780),4:(440,780),5:(440,400)}))
    # Common alternative traversals of fused and spiro skeletons.
    candidates.extend([
        ('C1CC2(C1)CCC2', {0:(215,595),1:(405,595),2:(405,405),3:(215,405),
                           4:(595,405),5:(595,215),6:(405,215)}),
        ('C1CCC2CCCCC2C1', {0:(120,500),1:(215,665),2:(405,665),3:(500,500),
                            4:(690,500),5:(785,335),6:(690,170),7:(500,170),
                            8:(405,335),9:(215,335)}),
    ])
    seen, result = set(), []
    for source, positions in candidates:
        atoms, edges = graph(source)
        signature = tuple((e.a,e.b,bool(e.ring)) for e in edges)
        if signature in seen:
            continue
        seen.add(signature)
        # Keep every scaffold in the font's positive canvas coordinates.
        min_x, min_y = min(p[0] for p in positions.values()), min(p[1] for p in positions.values())
        positions = {n:(round(x-min_x+110),round(y-min_y+180)) for n,(x,y) in positions.items()}
        result.append((source,atoms,edges,positions))
    return result
