# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Build standard Sim with a perfect font opponent on either side."""
import argparse
from math import hypot
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'shared'))
from exactgame import STATUS, LABELS
from fontgame import GameFont, circle, group
from game_text import NAME_RECORDS, centered_lettering
import model
from policy import SimPolicy
from layout import pack_layout

POINTS = ((900, 980), (1200, 820), (1200, 500), (900, 340), (600, 500), (600, 820))


def line(p, s, a, b, width, offset=0):
    x, y = a
    dx, dy = b[0]-x, b[1]-y
    length = hypot(dx, dy)
    nx, ny = -dy/length, dx/length
    x, y = s+x+nx*offset, y+ny*offset
    p.moveTo((x+nx*width/2, y+ny*width/2))
    p.lineTo((x+dx+nx*width/2, y+dy+ny*width/2))
    p.lineTo((x+dx-nx*width/2, y+dy-ny*width/2))
    p.lineTo((x-nx*width/2, y-ny*width/2))
    p.closePath()


def frame(p, s):
    centered_lettering(p, 'Sim', s+900, 1140, 20)
    centered_lettering(p, 'Avoid your own triangle', s+900, 1090, 9, weight='regular')
    for a, b in model.EDGES:
        line(p, s, POINTS[a], POINTS[b], 2)
    for i, (x, y) in enumerate(POINTS):
        circle(p, s+x, y, 17)
        centered_lettering(p, chr(65+i), s+900+(x-900)*1.18, 660+(y-660)*1.15-12, 11)
    centered_lettering(p, 'First: solid   Second: double', s+900, 230, 9, weight='regular')


def paint(f, board):
    parts = []
    for i, (a, b) in enumerate(model.EDGES):
        side = board//model.POWERS[i] % 3
        if not side:
            continue
        name = f'edge_{i}_{side}'
        if name not in f.glyphs:
            def draw(p, s, a=a, b=b, side=side):
                if side == 1:
                    line(p, s, POINTS[a], POINTS[b], 10)
                else:
                    for offset in (-6, 6):
                        line(p, s, POINTS[a], POINTS[b], 4, offset)
            f.add(name, draw)
        parts.append((name, side))
    return parts


def build_font(output):
    """One setup pass, eight human moves, and final terminal-tail cleanup.

    Each MOVE pass ligates one cursor/token pair. ERROR runs before MOVE so
    unmatched occupied edges stop at the valid prefix. Error marks retain the
    preceding board; all later input is deleted. No runtime solver is present.
    """
    from collections import deque
    import fontTools
    from fontTools.ttLib.tables.otBase import have_uharfbuzz
    if fontTools.__version__ != '4.50.0' or not have_uharfbuzz:
        raise RuntimeError('Sim requires its pinned build dependencies. Create the isolated environment documented in '+
                           str(Path(__file__).with_name('readme.md')))
    policy = SimPolicy()
    print(f'Policy closure: {len(policy.nodes)} states; human turns {policy.active_counts}')
    f = GameFont('Sim Perfect Opponent', 1800, 1250, name_records=NAME_RECORDS)
    raw = f.raw
    f.add('board', frame, advance=1800, overlay=False)
    ids = {node: i for i, node in enumerate(policy.nodes)}
    for human in (0, 1):
        text = 'You play first' if human == 0 else 'Font plays first'
        f.add(f'role_{human}', lambda p, s, text=text: centered_lettering(p, text, s+900, 165, 9, weight='regular'))
    def state(name, node, human):
        return f.layered(name, [*paint(f, node[0]), (f'role_{human}', 0)])
    header = state('r_header', model.INITIAL, 0)
    errors = {status: f.add('r_'+status) for status in ('invalid', 'malformed')}
    for status, code in STATUS.items():
        if status == 'draw':
            continue
        label = LABELS[code-1]
        f.add('status_'+status, lambda p, s, label=label: centered_lettering(p, label, s+900, 30, 11),
              advance=code, color=1 if code < 4 else 2)
    tokens = {token: f.add(f'move_{i}') for i, token in enumerate(model.TOKENS)}
    inputs = [*raw.values(), *tokens.values()]
    f.definitions += [
        f'lookup BAD_EDGE useExtension {{ sub {group(tokens.values())} by r_invalid; }} BAD_EDGE;',
        f'lookup BAD_SYNTAX useExtension {{ sub {group(inputs)} by r_malformed; }} BAD_SYNTAX;',
        'lookup FREEZE useExtension { '+ ' '.join(f'sub {glyph} by NULL;' for glyph in inputs)+' } FREEZE;',
    ]
    active, stopped, pending = {}, {}, deque()
    def cursor(node, human, status):
        if status == 'ready':
            if node not in active:
                active[node] = state(f'r_active_h{human}_{ids[node]}', node, human)
                pending.append(node)
            return active[node]
        key = node, human, status
        if key not in stopped:
            stopped[key] = state(f'r_{status}_h{human}_{ids[node]}', node, human)
        return stopped[key]
    moves, invalid = [], []
    for mode, human in (('h', 0), ('b', 1)):
        node, _, status = policy.settle(model.INITIAL, human)
        moves.append(f'sub {header} {raw[mode]} by {cursor(node, human, status)};')
    invalid.append(f'sub {header} {group(n for n in inputs if n not in (raw["h"], raw["b"]))}\' lookup BAD_SYNTAX;')
    count = 0
    while pending:
        node = pending.popleft()
        options, name = model.moves(node), active[node]
        bad = [glyph for token, glyph in tokens.items() if token not in options]
        if bad:
            invalid.append(f'sub {name} {group(bad)}\' lookup BAD_EDGE;')
        invalid.append(f'sub {name} {group(raw.values())}\' lookup BAD_SYNTAX;')
        for token, child in options.items():
            child, _, status = policy.settle(child, node[1])
            moves.append(f'sub {name} {tokens[token]} by {cursor(child, node[1], status)};')
        count += 1
        if count % 64 == 0:
            invalid.append('subtable;')
            moves.append('subtable;')
    states = [header, *active.values(), *stopped.values()]
    all_cursors = [*states, *errors.values()]
    frozen = [*stopped.values(), *errors.values()]
    freeze = []
    for offset in range(0, len(frozen), 512):
        freeze += [f'sub {group(frozen[offset:offset+512])} {group(inputs)}\' lookup FREEZE;', 'subtable;']
    f.lookup('SPACE', [f'sub {raw[" "]} by NULL;'], [raw[' ']])
    f.lookup('TOKENS', ['sub '+' '.join(raw[c] for c in token)+f' by {glyph};'
                        for token, glyph in tokens.items()], list(raw.values()))
    f.lookup('INIT', [f'sub begin by board {header};'], ['begin'])
    f.lookup('ERROR', [*freeze, *invalid], inputs, all_cursors)
    f.lookup('MOVE', moves, states, all_cursors)
    finish = [f'sub {header} end\' by status_malformed;', 'subtable;']
    def finish_group(names, status):
        for offset in range(0, len(names), 512):
            finish.extend([f'sub {group(names[offset:offset+512])} end\' by status_{status};', 'subtable;'])
    finish_group(list(active.values()), 'ready')
    for status in ('computer_won', 'human_won'):
        names = [name for (_, _, kind), name in stopped.items() if kind == status]
        finish_group(names, status)
    finish += [f'sub {name} end\' by status_{status};' for status, name in errors.items()]
    f.lookup('FINISH', finish, ['end'], all_cursors)
    # COLRv1 has 32-bit layer indices; this policy exceeds COLRv0's layer limit.
    # Keep identical glyf composites as the monochrome fallback.
    layers = f.layers
    f.layers = {name: {'Format': 1, 'Layers': [
        {'Format': 10, 'Glyph': part, 'Paint': {'Format': 2, 'PaletteIndex': color, 'Alpha': 1.0}}
        for part, color in parts]} for name, parts in layers.items()}
    return f.save(output, ['SPACE', 'TOKENS', 'INIT'], ['ERROR', 'MOVE'], ['ERROR', 'FINISH'], 9,
                  color_version=1, optimize_layout=pack_layout)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path(__file__).with_name('sim-font.ttf'))
    build_font(parser.parse_args().output)
