# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Retained third-party notices: see THIRD_PARTY_NOTICES.md at the project root.

"""Build the Snake font with dimensions supplied at runtime. Requires FontTools."""

import argparse
from pathlib import Path

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

UPM = 1000
MIN_W, MAX_W = (4, 10)
MIN_H, MAX_H = (4, 10)
MAX_MOVES = 8
CELL = 150
MAX_ASC = MAX_H * CELL + 100
MOVES = {'w': (0, 1), 'a': (-1, 0), 's': (0, -1), 'd': (1, 0)}


def empty_glyph():
    return TTGlyphPen(None).glyph()


def rectangle(p, x0, y0, x1, y1):
    p.moveTo((x0, y0))
    p.lineTo((x1, y0))
    p.lineTo((x1, y1))
    p.lineTo((x0, y1))
    p.closePath()


def cell_glyph(x, y):
    p = TTGlyphPen(None)
    x0 = x * CELL
    y0 = y * CELL
    t = 5
    rectangle(p, x0, y0, x0 + CELL, y0 + t)
    rectangle(p, x0, y0 + CELL - t, x0 + CELL, y0 + CELL)
    rectangle(p, x0, y0, x0 + t, y0 + CELL)
    rectangle(p, x0 + CELL - t, y0, x0 + CELL, y0 + CELL)
    return p.glyph()


def body_glyph(x, y):
    p = TTGlyphPen(None)
    x0 = x * CELL
    y0 = y * CELL
    i = 34
    rectangle(p, x0 + i, y0 + i, x0 + CELL - i, y0 + CELL - i)
    return p.glyph()


def head_glyph(x, y):
    p = TTGlyphPen(None)
    x0 = x * CELL
    y0 = y * CELL
    i = 24
    rectangle(p, x0 + i, y0 + i, x0 + CELL - i, y0 + CELL - i)
    e = 12
    rectangle(p, x0 + CELL - i - 2 * e, y0 + CELL - i - 2 * e, x0 + CELL - i - e, y0 + CELL - i - e)
    return p.glyph()


def food_glyph(x, y):
    p = TTGlyphPen(None)
    cx = x * CELL + CELL / 2
    cy = y * CELL + CELL / 2
    r = 18
    p.moveTo((cx, cy + r))
    p.lineTo((cx + r, cy))
    p.lineTo((cx, cy - r))
    p.lineTo((cx - r, cy))
    p.closePath()
    return p.glyph()


def dead_glyph(x, y):
    p = TTGlyphPen(None)
    x0 = x * CELL
    y0 = y * CELL
    t = 10
    # The corner-to-corner X stays visible outside the inset head.
    for i in range(7):
        q = 7 + i * 21
        rectangle(p, x0 + q, y0 + q, x0 + q + t, y0 + q + t)
        rectangle(p, x0 + (CELL - q - t), y0 + q, x0 + (CELL - q), y0 + q + t)
    return p.glyph()


def food_position(width, height):
    return (width - 1, min(height - 1, height // 2 + MAX_MOVES - (width - 3)))


def win_glyph(width, height):
    p = TTGlyphPen(None)
    x, y = food_position(width, height)
    x0 = x * CELL
    y0 = y * CELL
    i = 24
    rectangle(p, x0 + i, y0 + i, x0 + CELL - i, y0 + CELL - i)
    rectangle(p, x0 + 35, y0 + CELL + 12, x0 + 55, y0 + CELL + 32)
    rectangle(p, x0 + 60, y0 + CELL + 24, x0 + 82, y0 + CELL + 44)
    rectangle(p, x0 + 85, y0 + CELL + 12, x0 + 105, y0 + CELL + 32)
    return p.glyph()


def digit_name(c):
    return f'digit{c}'


def cell_name(x, y):
    return f'cell_{x}_{y}'


def body_name(x, y):
    return f'body_{x}_{y}'


def head_name(x, y):
    return f'head_{x}_{y}'


def food_name(x, y):
    return f'food_{x}_{y}'


def dead_name(x, y):
    return f'dead_{x}_{y}'


def init_name(width, height):
    return f'init_{width}_{height}'


def dimension_name(width, height):
    return f'dim_{width}_{height}'


def swap_name(width, height, x, y):
    return f'swap_{width}_{height}_{x}_{y}'


def win_name(width, height):
    return f'win_{width}_{height}'


def build_font(output):
    chars = list('0123456789xbwasd')
    names = {c: digit_name(c) if c.isdigit() else c for c in chars}
    order = ['.notdef', 'ghost'] + list(dict.fromkeys(names.values()))
    glyphs = {'.notdef': empty_glyph(), 'ghost': empty_glyph()}
    metrics = {'.notdef': (500, 0), 'ghost': (0, 0)}
    for n in dict.fromkeys(names.values()):
        glyphs[n] = empty_glyph()
        metrics[n] = (0, 0)
    for y in range(MAX_H):
        for x in range(MAX_W):
            items = [
                (cell_name(x, y), cell_glyph(x, y), x * CELL),
                (body_name(x, y), body_glyph(x, y), x * CELL + 34),
                (head_name(x, y), head_glyph(x, y), x * CELL + 24),
                (food_name(x, y), food_glyph(x, y), x * CELL + CELL // 2 - 18),
                (dead_name(x, y), dead_glyph(x, y), x * CELL + 7),
            ]
            for n, g, lsb in items:
                order.append(n)
                glyphs[n] = g
                metrics[n] = (1 if n.startswith('dead_') else 0, lsb)
    for width in range(MIN_W, MAX_W + 1):
        for height in range(MIN_H, MAX_H + 1):
            board_items = [
                (init_name(width, height), empty_glyph(), 0),
                (dimension_name(width, height), empty_glyph(), 0),
                (win_name(width, height), win_glyph(width, height), (width - 1) * CELL + 24),
            ]
            for n, g, lsb in board_items:
                order.append(n)
                glyphs[n] = g
                metrics[n] = (2 if n.startswith('win_') else 0, lsb)
            for y in range(height):
                for x in range(width):
                    n = swap_name(width, height, x, y)
                    order.append(n)
                    glyphs[n] = empty_glyph()
                    metrics[n] = (0, 0)
    fb = FontBuilder(UPM, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({ord(c): names[c] for c in chars})
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=MAX_ASC, descent=-100)
    fb.setupNameTable({
        'familyName': 'Snake Dynamic Board',
        'styleName': 'Regular',
        'uniqueFontIdentifier': 'SnakeDynamicBoard-6.3',
        'fullName': 'Snake Dynamic Board',
        'psName': 'SnakeDynamicBoard-Regular',
        'version': 'Version 6.3',
        16: 'Snake Dynamic Board',
        17: 'Regular',
        'copyright': 'Copyright 2026 Michael Brackx',
        'licenseDescription': 'Licensed under the Apache License, Version 2.0',
        'licenseInfoURL': 'https://www.apache.org/licenses/LICENSE-2.0',
    })
    fb.setupOS2(sTypoAscender=MAX_ASC, sTypoDescender=-100, usWinAscent=MAX_ASC, usWinDescent=100)
    fb.setupPost()
    fb.setupMaxp()
    font = fb.font
    fea = ['languagesystem DFLT dflt;', '@MOVES = [w a s d];']
    dimensions = [dimension_name(width, height)
                  for width in range(MIN_W, MAX_W + 1)
                  for height in range(MIN_H, MAX_H + 1)]
    heads = [head_name(x, y) for y in range(MAX_H) for x in range(MAX_W)]
    bodies = [body_name(x, y) for y in range(MAX_H) for x in range(MAX_W)]
    fea.append('@DIM = [' + ' '.join(dimensions) + '];')
    fea.append('@HEAD = [' + ' '.join(heads) + '];')
    fea.append('@BODY = [' + ' '.join(bodies) + '];')
    # Parse the dimensions before expanding reusable cell glyphs.
    fea.append('lookup PARSE {')
    for width in range(MIN_W, MAX_W + 1):
        for height in range(MIN_H, MAX_H + 1):
            seq = ' '.join((names[c] for c in list(str(width) + 'x' + str(height) + 'b')))
            fea.append(f' sub {seq} by {init_name(width, height)};')
    fea.append('} PARSE;')
    # The state suffix is: body, body, dimension, head.
    fea.append('lookup EXPAND {')
    for width in range(MIN_W, MAX_W + 1):
        for height in range(MIN_H, MAX_H + 1):
            y0 = height // 2
            out = [cell_name(x, y) for y in range(height) for x in range(width)]
            out += [food_name(*food_position(width, height)), body_name(0, y0), body_name(1, y0), dimension_name(width, height), head_name(2, y0)]
            fea.append(f' sub {init_name(width, height)} by ' + ' '.join(out) + ';')
    fea.append('} EXPAND;')
    # The neck directly before the dimension token detects reversal.
    fea.append('lookup REVERSE {')
    for y in range(MAX_H):
        for x in range(MAX_W):
            for c, (dx, dy) in MOVES.items():
                tx, ty = (x + dx, y + dy)
                if 0 <= tx < MAX_W and 0 <= ty < MAX_H:
                    fea.append(f" sub {body_name(tx, ty)} @DIM {head_name(x, y)} {c}' by {dead_name(x, y)};")
    fea.append('} REVERSE;')
    # Wall and food rules depend on board dimensions.
    fea.append('lookup SPECIAL {')
    winprev = []
    for width in range(MIN_W, MAX_W + 1):
        for height in range(MIN_H, MAX_H + 1):
            dim = dimension_name(width, height)
            food = food_position(width, height)
            for y in range(height):
                for x in range(width):
                    for c, (dx, dy) in MOVES.items():
                        tx, ty = (x + dx, y + dy)
                        if not (0 <= tx < width and 0 <= ty < height):
                            fea.append(f" sub {dim} {head_name(x, y)} {c}' by {dead_name(x, y)};")
                        elif (tx, ty) == food:
                            fea.append(f" sub {dim} {head_name(x, y)} {c}' by {win_name(width, height)};")
                            winprev.append((width, height, x, y))
    fea.append('} SPECIAL;')
    # Normal moves discard the oldest body cell before appending the old head.
    fea.append('lookup DROP_TAIL {')
    fea.append(" sub @BODY' @BODY @DIM @HEAD @MOVES by ghost;")
    fea.append('} DROP_TAIL;')
    fea.append('lookup STEP {')
    for y in range(MAX_H):
        for x in range(MAX_W):
            for c, (dx, dy) in MOVES.items():
                tx, ty = (x + dx, y + dy)
                if 0 <= tx < MAX_W and 0 <= ty < MAX_H:
                    fea.append(f" sub @DIM {head_name(x, y)} {c}' by {head_name(tx, ty)};")
    fea.append('} STEP;')
    fea.append('lookup OLDTOBODY {')
    for y in range(MAX_H):
        for x in range(MAX_W):
            fea.append(f" sub {head_name(x, y)}' @HEAD by {body_name(x, y)};")
    fea.append('} OLDTOBODY;')
    fea.append('lookup SWAP1 {')
    for width in range(MIN_W, MAX_W + 1):
        for height in range(MIN_H, MAX_H + 1):
            for y in range(height):
                for x in range(width):
                    fea.append(f' sub {dimension_name(width, height)} {body_name(x, y)} by {swap_name(width, height, x, y)};')
    fea.append('} SWAP1;')
    fea.append('lookup SWAP2 {')
    for width in range(MIN_W, MAX_W + 1):
        for height in range(MIN_H, MAX_H + 1):
            for y in range(height):
                for x in range(width):
                    fea.append(f' sub {swap_name(width, height, x, y)} by {body_name(x, y)} {dimension_name(width, height)};')
    fea.append('} SWAP2;')
    fea.append('lookup WINBODY {')
    for width, height, x, y in winprev:
        fea.append(f" sub {head_name(x, y)}' {win_name(width, height)} by {body_name(x, y)};")
    fea.append('} WINBODY;')
    fea.append('feature liga { lookup PARSE; lookup EXPAND;')
    fea += [f' lookup {name};' for name in (
        'REVERSE', 'SPECIAL', 'DROP_TAIL', 'STEP',
        'OLDTOBODY', 'SWAP1', 'SWAP2', 'WINBODY',
    )]
    fea += ['} liga;']
    fea_text = '\n'.join(fea)
    addOpenTypeFeaturesFromString(font, fea_text)
    # Distinct wrapper indices provide clock passes; contextual rules reuse
    # the original helper lookups to avoid duplicating substitution maps.
    feature = font['GSUB'].table.FeatureList.FeatureRecord[0].Feature
    lookup_list = font['GSUB'].table.LookupList
    top = list(feature.LookupListIndex)
    if len(top) != 10:
        raise RuntimeError(f'expected 10 top-level lookups, got {len(top)}: {top}')
    parse_expand = top[:2]
    cycle = top[2:]
    feature_indices = parse_expand + cycle
    for _ in range(MAX_MOVES - 1):
        cloned_cycle = []
        for idx in cycle:
            lookup_list.Lookup.append(lookup_list.Lookup[idx])
            cloned_cycle.append(len(lookup_list.Lookup) - 1)
        feature_indices += cloned_cycle
    lookup_list.LookupCount = len(lookup_list.Lookup)
    feature.LookupListIndex = feature_indices
    feature.LookupCount = len(feature_indices)
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    font.save(out)
    font.close()
    print(f'Saved {out}: sizes {MIN_W}-{MAX_W} x {MIN_H}-{MAX_H}, up to {MAX_MOVES} moves')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--output', type=Path,
        default=Path(__file__).resolve().with_name('snake-dynamic-font.ttf'),
        help='output .ttf path (default: snake-dynamic-font.ttf beside this script)',
    )
    args = parser.parse_args()
    build_font(args.output)


if __name__ == '__main__':
    main()
