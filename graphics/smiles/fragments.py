# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Compile disconnected component boundaries and spacing into OpenType."""


def parser(add, lookup, chars, states, max_atoms):
    gap = add('fragment_gap')
    counts = {n:add(f'fragment_gap_{n}') for n in range(1,max_atoms+1)}
    # Split only after an active, completed outer atom. Bare input stays
    # readable. Closing-brace and gap glyphs prevent parser operations from
    # crossing a fragment boundary while each component finishes shaping.
    lookup('FRAGMENT_DOT_EXPAND',[
        f'sub {chars["."]} by {chars["}"]} {gap} {chars["{"]};'
    ],'0')
    complete = [name for (n,last,d,bond,pending),name in states.items()
                if d==0 and bond==0 and not pending]
    lookup('FRAGMENT_SPLIT',[
        f"sub [{' '.join(complete)}] {chars['.']}' lookup FRAGMENT_DOT_EXPAND;"
    ])
    lookup('FRAGMENT_COUNT',[
        f"sub [{' '.join(name for (nn,last,d,bond,pending),name in states.items() if nn==n and d==0 and bond==0 and not pending)}] {chars['}']} {gap}' by {counts[n]};"
        for n in counts
    ])
    return counts


def spacing(features, counts, layouts, width, point):
    # Each component retains the full canvas advance until its bracket marks
    # have attached. A later empty separator then removes unused canvas space.
    # This also keeps GPOS bracket anchors local to their own component.
    steps = {n:point(n-1,0)[0]+400 for n in counts}
    features.append('lookup FRAGMENT_BASE_SPACE useExtension { lookupflag 0;')
    features.extend(f'pos {name} <0 0 {steps[n]-width} 0>;' for n,name in counts.items())
    features.append('} FRAGMENT_BASE_SPACE;')
    features.append('lookup FRAGMENT_LAYOUT_SPACE useExtension { lookupflag IgnoreMarks;')
    for index,(_,vertices,_,positions) in enumerate(layouts):
        count = len(vertices)
        adjustment = max(x for x,y in positions.values())+400-steps[count]
        if adjustment:
            features.append(f"pos layout_{index} {counts[count]}' <0 0 {adjustment} 0>;")
            features.append('subtable;')
    features.append('} FRAGMENT_LAYOUT_SPACE;')
    features.append('feature calt { lookup FRAGMENT_BASE_SPACE; lookup FRAGMENT_LAYOUT_SPACE; } calt;')
