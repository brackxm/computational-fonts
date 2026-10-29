# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Lossless storage helpers for the repository's static TrueType fonts."""
from collections import Counter
from array import array

from .layout import compact_layout
from .web import compact_woff2
from .runs import compact_runs

from fontTools.ttLib.tables._g_l_y_f import (
    Glyph, GlyphCoordinates, GlyphComponent, USE_MY_METRICS, OVERLAP_COMPOUND, flagOverlapSimple,
)
from fontTools.ttLib.tables.ttProgram import Program


def _unhinted(glyph):
    program = getattr(glyph, 'program', None)
    return program is None or not program.getBytecode()


def _component(name, x=0, y=0):
    component = GlyphComponent()
    component.glyphName = name
    component.x, component.y = x, y
    component.flags = 4  # ROUND_XY_TO_GRID; helper parents stay at the origin.
    return component


def _composite(components):
    glyph = Glyph()
    glyph.numberOfContours = -1
    glyph.components = components
    return glyph


def compact_glyphs(font, *, rounds=4, positioned=False, min_uses=16):
    """Share duplicate unhinted outlines and exact component pairs.

    Existing glyph names, IDs, metrics, cmap, instructions and layout tables
    stay intact. Helpers are appended, have zero advance, and have no character
    mappings. By default only identity components at (0, 0) participate in
    pair sharing. positioned=True also shares exact positioned components;
    their coordinates and flags stay inside the helper, whose parent is still
    at the origin. No offsets are normalized or split across parent and child.
    Variable fonts are excluded because their glyph deltas would need remapping.
    Lower repetition thresholds also charge each helper's storage overhead.
    """
    if 'glyf' not in font or any(tag in font for tag in ('gvar', 'fvar', 'VARC', 'HVAR', 'VVAR')):
        return {'aliases': 0, 'pairs': 0}
    glyf = font['glyf']
    order = list(font.getGlyphOrder())
    originals = tuple(order)
    seen = {}
    aliases = 0
    for name in originals:
        glyph = glyf[name]
        if not glyph.numberOfContours or not _unhinted(glyph):
            continue
        # These flags belong to their original glyph level. Introducing a
        # parent could change delegated grid-fitted metrics or overlap handling.
        if glyph.isComposite():
            if any(part.flags & (USE_MY_METRICS | OVERLAP_COMPOUND) for part in glyph.components):
                continue
        elif glyph.flags[0] & flagOverlapSimple:
            continue
        data = glyph.compile(glyf)
        if data in seen and len(data) > 16:
            replacement = _composite([_component(seen[data])])
            # Retain the existing bounds exactly; only storage changes.
            for field in ('xMin', 'yMin', 'xMax', 'yMax'):
                setattr(replacement, field, getattr(glyph, field))
            glyf[name] = replacement
            aliases += 1
        else:
            seen.setdefault(data, name)

    # These auxiliary tables carry one entry per glyph. Retain their original
    # coverage rather than appending helpers that those tables do not describe.
    if any(tag in font for tag in ('vmtx', 'hdmx', 'LTSH', 'sbix', 'CBDT', 'CBLC', 'EBDT', 'EBLC', 'SVG ')):
        return {'aliases': aliases, 'pairs': 0}

    def eligible(glyph):
        return (glyph.isComposite() and _unhinted(glyph) and
                all(set(vars(part)) <= {'glyphName', 'x', 'y', 'flags'} and
                    (positioned or part.x == part.y == 0) and part.flags == 4
                    for part in glyph.components))

    pairs = 0
    for _ in range(rounds):
        streams = {name: [(part.glyphName, part.x, part.y) for part in glyf[name].components]
                   for name in originals if eligible(glyf[name])}
        counts = Counter(pair for stream in streams.values() for pair in zip(stream, stream[1:]))
        candidates = {pair for pair, count in counts.items() if count >= min_uses}
        if not candidates:
            break
        plans = {}
        uses = Counter()
        for name, stream in streams.items():
            plan = []
            at = 0
            while at < len(stream):
                pair = tuple(stream[at:at+2])
                if pair in candidates:
                    plan.append(pair)
                    uses[pair] += 1
                    at += 2
                else:
                    plan.append(stream[at])
                    at += 1
            plans[name] = plan
        helpers = {}
        for pair, count in sorted(uses.items(), key=lambda item: (-item[1], item[0])):
            if count < min_uses or len(order) >= 65534:
                continue
            name = f'_share{pairs}'
            while name in glyf:
                name = '_' + name
            helper = _composite([_component(*part) for part in pair])
            if min_uses < 16:
                # Each replaced pair saves six component bytes. Charge a long
                # loca offset, a full metric, a format-2 post name/index, and
                # table alignment before accepting less frequent helpers.
                overhead = len(helper.compile(glyf))+8+3+len(name)+4
                if count*6 <= overhead:
                    continue
            glyf[name] = helper
            helper.recalcBounds(glyf)
            font['hmtx'].metrics[name] = (0, helper.xMin)
            order.append(name)
            helpers[pair] = name
            pairs += 1
        if not helpers:
            break
        for name, plan in plans.items():
            parts = []
            for item in plan:
                if len(item) == 2:
                    parts.extend([_component(helpers[item])] if item in helpers else
                                 [_component(*part) for part in item])
                else:
                    parts.append(_component(*item))
            glyf[name].components = parts
    if pairs:
        font.setGlyphOrder(order)
        glyf.glyphOrder = order
    return {'aliases': aliases, 'pairs': pairs}


def compact_contours(font, *, rounds=4, min_uses=8):
    """Share exact ordered contour runs in unhinted static simple glyphs.

    Helpers retain original positions, curve flags, winding and point order.
    Parents reference them at the origin; no coordinates are normalized.
    Existing glyph IDs, cmap, metrics and instructions stay intact. Estimated
    helper, metric and name overhead must pay for itself before replacement.
    Overlap-marked glyphs, variable fonts and per-glyph caches are excluded.
    """
    excluded = ('gvar', 'fvar', 'VARC', 'HVAR', 'VVAR', 'vmtx', 'hdmx', 'LTSH',
                'sbix', 'CBDT', 'CBLC', 'EBDT', 'EBLC', 'SVG ')
    if 'glyf' not in font or any(tag in font for tag in excluded):
        return {'glyphs': 0, 'helpers': 0}
    glyf = font['glyf']
    order = list(font.getGlyphOrder())
    streams, old_sizes = {}, {}
    for name in order:
        glyph = glyf[name]
        if (glyph.numberOfContours <= 1 or not _unhinted(glyph) or
                glyph.flags[0] & flagOverlapSimple):
            continue
        stream, start = [], 0
        for end in glyph.endPtsOfContours:
            contour = (tuple(glyph.coordinates[start:end+1]),
                       bytes(glyph.flags[start:end+1]))
            stream.append((contour,))
            start = end+1
        streams[name] = stream
        old_sizes[name] = len(glyph.compile(glyf))

    # Discover longer runs without changing their exact contour sequence.
    for _ in range(rounds):
        counts = Counter(pair for stream in streams.values()
                         for pair in zip(stream, stream[1:]))
        candidates = {pair for pair, count in counts.items() if count >= min_uses}
        if not candidates:
            break
        for name, stream in streams.items():
            parts, at = [], 0
            while at < len(stream):
                if at+1 < len(stream) and (stream[at], stream[at+1]) in candidates:
                    parts.append(stream[at]+stream[at+1])
                    at += 2
                else:
                    parts.append(stream[at])
                    at += 1
            streams[name] = parts
    counts = Counter(part for stream in streams.values() for part in stream)
    shared = {part for part, count in counts.items() if count >= min_uses}
    plans = {}
    for name, stream in streams.items():
        parts, tail = [], ()
        for part in stream:
            if part in shared:
                if tail:
                    parts.append(tail)
                    tail = ()
                parts.append(part)
            else:
                tail += part
        if tail:
            parts.append(tail)
        plans[name] = parts

    def simple(contours):
        glyph = Glyph()
        glyph.numberOfContours = len(contours)
        glyph.coordinates = GlyphCoordinates()
        glyph.flags = array('B')
        glyph.endPtsOfContours = []
        for points, flags in contours:
            glyph.coordinates.extend(points)
            glyph.flags.extend(flags)
            glyph.endPtsOfContours.append(len(glyph.coordinates)-1)
        glyph.program = Program()
        glyph.program.fromBytecode(b'')
        glyph.recalcBounds(glyf)
        return glyph

    # Charge each helper's complete outline plus its name, loca and hmtx entry.
    # Re-evaluate after removing unprofitable glyphs, since fewer remaining
    # users must then pay for each shared helper.
    sizes = {}
    while plans:
        uses = Counter(part for parts in plans.values() for part in parts)
        for part in uses:
            if part not in sizes:
                sizes[part] = len(simple(part).compile(glyf))+24
        kept = {name: parts for name, parts in plans.items()
                if 10+6*len(parts)+sum(sizes[part]/uses[part] for part in parts)+4
                < old_sizes[name]}
        if len(kept) == len(plans):
            break
        plans = kept
    if not plans:
        return {'glyphs': 0, 'helpers': 0}
    uses = Counter(part for parts in plans.values() for part in parts)
    if len(order)+len(uses) >= 65535:
        return {'glyphs': 0, 'helpers': 0}
    names = {}
    for part in uses:
        name = f'_contour{len(names)}'
        while name in glyf:
            name = '_'+name
        glyph = simple(part)
        glyf[name] = glyph
        font['hmtx'].metrics[name] = (0, glyph.xMin)
        order.append(name)
        names[part] = name
    for name, parts in plans.items():
        old = glyf[name]
        replacement = _composite([_component(names[part]) for part in parts])
        for field in ('xMin', 'yMin', 'xMax', 'yMax'):
            setattr(replacement, field, getattr(old, field))
        glyf[name] = replacement
    font.setGlyphOrder(order)
    glyf.setGlyphOrder(order)
    return {'glyphs': len(plans), 'helpers': len(uses)}
