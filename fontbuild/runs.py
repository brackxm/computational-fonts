# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Share profitable component sequences in top-level static artwork."""
from collections import Counter

from fontTools.misc.roundTools import otRound


def compact_runs(font, *, lengths=(8, 6, 4, 3), positioned=False):
    """Share exact ordered runs without moving, removing or renaming glyphs.

    Only unhinted, unreferenced composite roots participate. Their children
    stay intact, so an inserted helper cannot increase an ancestor's depth.
    Components retain their positions and flags; helper references use (0, 0).
    Actual non-overlapping uses must cover outline, metric, location, name and
    alignment costs. Variable fonts and per-glyph caches retain their encoding.
    """
    from . import _component, _composite, _unhinted

    lengths = tuple(lengths)
    excluded = ('gvar', 'fvar', 'VARC', 'HVAR', 'VVAR', 'vmtx', 'hdmx', 'LTSH',
                'sbix', 'CBDT', 'CBLC', 'EBDT', 'EBLC', 'SVG ')
    if 'glyf' not in font or any(tag in font for tag in excluded):
        return {'helpers': 0, 'uses': 0}
    if any(length < 3 for length in lengths):
        raise ValueError('Component runs must contain at least three components')
    glyf = font['glyf']
    order = list(font.getGlyphOrder())
    referenced = {part.glyphName for name in order if glyf[name].isComposite()
                  for part in glyf[name].components}

    def eligible(glyph):
        return (glyph.isComposite() and _unhinted(glyph) and
                all(set(vars(part)) <= {'glyphName', 'x', 'y', 'flags'} and
                    part.flags == 4 and (positioned or part.x == part.y == 0)
                    for part in glyph.components))

    roots = [name for name in order
             if name not in referenced and eligible(glyf[name])]
    depths = {}

    def depth(name):
        if name not in depths:
            glyph = glyf[name]
            depths[name] = (1+max((depth(part.glyphName)
                                  for part in glyph.components), default=-1)
                            if glyph.isComposite() else 0)
        return depths[name]

    def record_size(part):
        # Match GlyphComponent.compile's rounding and byte/word argument choice.
        return (6 if -128 <= otRound(part[1]) <= 127 and
                -128 <= otRound(part[2]) <= 127 else 8)

    made, total_uses = 0, 0
    for length in lengths:
        streams = {name: tuple((part.glyphName, part.x, part.y)
                              for part in glyf[name].components)
                   for name in roots}
        counts = Counter(stream[i:i+length] for stream in streams.values()
                         for i in range(len(stream)-length+1))

        def profitable(run, count):
            encoded = sum(record_size(part) for part in run)
            # Use a conservative name length during planning; charge the exact
            # name again when allocating. The root adds one more glyph level.
            cost = 10+encoded+8+3+12+4
            return (count >= 2 and count*(encoded-6) > cost and
                    max(depth(part[0]) for part in run)+2 <= 16)

        candidates = {run for run, count in counts.items()
                      if profitable(run, count)}
        while candidates:
            plans, uses = {}, Counter()
            for name, stream in streams.items():
                plan, at = [], 0
                while at < len(stream):
                    run = stream[at:at+length]
                    if run in candidates:
                        plan.append((True, run))
                        uses[run] += 1
                        at += length
                    else:
                        plan.append((False, stream[at]))
                        at += 1
                plans[name] = plan
            kept = {run for run, count in uses.items() if profitable(run, count)}
            if kept == candidates:
                break
            candidates = kept
        if not candidates:
            continue
        helpers = {}
        for run, count in sorted(uses.items(), key=lambda item: (-item[1], item[0])):
            if run not in candidates or len(order) >= 65534:
                continue
            name = f'_run{made}'
            while name in glyf:
                name = '_'+name
            helper = _composite([_component(*part) for part in run])
            cost = len(helper.compile(glyf))+8+3+len(name)+4
            if count*(sum(record_size(part) for part in run)-6) <= cost:
                continue
            glyf[name] = helper
            helper.recalcBounds(glyf)
            font['hmtx'].metrics[name] = (0, helper.xMin)
            order.append(name)
            helpers[run] = name
            made += 1
            total_uses += count
        for name, plan in plans.items():
            parts = []
            for grouped, value in plan:
                if grouped:
                    parts.extend([_component(helpers[value])] if value in helpers
                                 else [_component(*part) for part in value])
                else:
                    parts.append(_component(*value))
            glyf[name].components = parts
            depths.pop(name, None)
    if made:
        font.setGlyphOrder(order)
        glyf.setGlyphOrder(order)
    return {'helpers': made, 'uses': total_uses}
