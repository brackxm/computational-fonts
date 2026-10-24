# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Compile an independently generated endgame certificate to an OpenType font.

Research only: b selects a fixed, explicitly supplied endgame position. Human
digits are consumed, Red replies and the final board is drawn entirely by GSUB.
No WeakC4 data or GPL-labelled production modules are imported.
"""
from __future__ import annotations

import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import sys
import time

from independent import Exact, array_board, check_certificate, parse, ranked, synthesize_cells

SHARED = Path(__file__).resolve().parents[2] / 'shared'
sys.path.insert(0, str(SHARED))
from fontgame import GameFont, circle, group, rect

# The shaping harness is Apache-2.0 and contains no game logic or policy.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shaping import Shaper


def collapsed(certificate):
    """Fold each prescribed Red reply into the preceding human transition."""
    nodes = certificate['nodes']
    transitions, pending, seen = {}, deque([certificate['root']]), set()
    while pending:
        key = pending.popleft()
        if key in seen:
            continue
        seen.add(key)
        node = nodes[key]
        if 'terminal' in node:
            transitions[key] = {}
            continue
        if not key.endswith('/2'):
            raise ValueError('probe requires a Yellow-to-move root')
        edges = {}
        for human, child in node['edges'].items():
            if 'terminal' not in nodes[child]:
                child, = nodes[child]['edges'].values()
            edges[human] = child
            pending.append(child)
        transitions[key] = edges
    return transitions


def build_probe(certificate, history, output):
    check_certificate(certificate, history)
    transitions = collapsed(certificate)
    f = GameFont('Independent C4 Endgame Research', 1000, 900)
    f.palette = ('233f48', 'd54738', 'edbc40', 'e1e8df')
    raw = [*f.raw.values(), '.notdef']

    def grid(pen, shift):
        for x in range(8):
            rect(pen, 45+130*x, 90, 4, 660)
        for y in range(7):
            rect(pen, 45, 90+110*y, 914, 4)

    f.add('grid', grid, overlay=False)
    for col in range(7):
        for row in range(6):
            for player in (1, 2):
                def disc(pen, shift, col=col, row=row, player=player):
                    circle(pen, 110+130*col, 145+110*row, 40)
                    if player == 2:
                        circle(pen, 110+130*col, 145+110*row, 29, reverse=True)
                f.add(f'disc_{col}_{row}_{player}', disc, overlay=False)

    names, failed = {}, {}

    def state(key, status):
        red, yellow, _ = (int(part, 16) for part in key.split('/'))
        board = array_board(red, yellow)
        components = ['grid']+[f'disc_{c}_{r}_{board[r][c]}'
                               for r in range(6) for c in range(7) if board[r][c]]

        def draw(pen, shift):
            for component in components:
                pen.addComponent(component, (1, 0, 0, 1, 0, 0))

        return f.add(f'r_{len(names)}_{status}', draw, advance=1000+status, overlay=False)

    for key, edges in transitions.items():
        names[key] = state(key, 1 if edges else 2)
    for key, edges in transitions.items():
        if edges:
            # Different prefix preserves a unique glyph name for the same board.
            failed[key] = f.add(f'r_failed_{len(failed)}',
                                lambda p, s, key=key: p.addComponent(names[key], (1, 0, 0, 1, 0, 0)),
                                advance=1003, overlay=False)

    all_states = [*names.values(), *failed.values()]
    stopped = [names[key] for key, edges in transitions.items() if not edges]+list(failed.values())
    init = [f'ignore sub {group(f.order)} {f.raw["b"]}\';',
            f'sub {f.raw["b"]}\' by {names[certificate["root"]]};']
    f.lookup('INIT', init, [f.raw['b']])
    rules = [f'sub {group(stopped)} {group(raw)}\' by NULL;']
    for key, edges in transitions.items():
        if not edges:
            continue
        rules.extend(f'sub {names[key]} {f.raw[human]}\' by {names[child]};'
                     for human, child in sorted(edges.items()))
        bad = [name for char, name in f.raw.items() if char not in edges]+['.notdef']
        rules.append(f'sub {names[key]} {group(bad)}\' by {failed[key]};')
    f.lookup('PLAY', rules, raw)
    f.lookup('CLEAN', [f'sub {group(all_states)}\' {group(all_states)} by NULL;'], all_states)
    glyphs, lookups, size = f.save(output, ['INIT', 'PLAY', 'CLEAN'], [], [], 1)
    return transitions, names, failed, {'glyphs': glyphs, 'lookups': lookups, 'ttf_bytes': size}


def verify_probe(certificate, transitions, names, failed, output):
    """Real HarfBuzz calls on human histories covering every reachable edge."""
    root = certificate['root']
    witnesses, pending = {root: 'b'}, deque([root])
    while pending:
        key = pending.popleft()
        for human, child in transitions[key].items():
            if child not in witnesses:
                witnesses[child] = witnesses[key]+human
                pending.append(child)
    checks, timings = 0, []
    shaper = Shaper(output)
    try:
        def check(source, expected):
            nonlocal checks
            begin = time.perf_counter()
            shaped = shaper.run(source)
            timings.append((time.perf_counter()-begin)*1000)
            if len(shaped) != 1 or shaped[0][0] != expected:
                raise AssertionError((source, expected, shaped))
            checks += 1

        for key, prefix in witnesses.items():
            check(prefix, names[key])
            for human, child in transitions[key].items():
                check(prefix+human, names[child])
            if transitions[key]:
                check(prefix+'!', failed[key])
                for human in '1234567':
                    if human not in transitions[key]:
                        check(prefix+human, failed[key])
            else:
                check(prefix+'1234567', names[key])
        if shaper.run('b', enabled=False) == shaper.run('b'):
            raise AssertionError('probe must depend on GSUB')
        version = shaper.version
    finally:
        shaper.close()
    timings.sort()
    return {'harfbuzz': version, 'history_shapes': checks,
            'reachable_cursor_states': len(witnesses),
            'maximum_human_inputs': max(map(len, witnesses.values()))-1,
            'median_ms': round(timings[len(timings)//2], 4),
            'max_ms': round(max(timings), 4)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history', default='77111372676733526176246')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--policy', choices=('exact', 'synthesized'), default='synthesized')
    args = parser.parse_args()
    engine = Exact(250000)
    synthesis = None
    if args.policy == 'synthesized':
        synthesis = synthesize_cells(args.history)
        if synthesis['status'] != 'verified':
            raise ValueError('no verified compact policy for this root')
        priorities = synthesis['priorities_column_major_bottom_up']
        certificate = engine.certificate(*parse(args.history), choose=lambda r, y: ranked(r, y, priorities))
    else:
        certificate = engine.certificate(*parse(args.history))
    report = {'scope': 'fixed endgame only; no empty-board guarantee',
              'history': args.history,
              'policy': args.policy,
              'certificate': check_certificate(certificate, args.history)}
    if synthesis:
        report['synthesis'] = synthesis
    transitions, names, failed, stats = build_probe(certificate, args.history, args.output)
    report['font'] = stats
    from fontTools.ttLib import TTFont
    with TTFont(args.output) as font:
        font.flavor = 'woff2'
        woff = args.output.with_suffix('.woff2')
        font.save(woff)
    report['font']['woff2_bytes'] = woff.stat().st_size
    report['font']['ttf_sha256'] = hashlib.sha256(args.output.read_bytes()).hexdigest()
    report['font']['woff2_sha256'] = hashlib.sha256(woff.read_bytes()).hexdigest()
    report['shaping'] = verify_probe(certificate, transitions, names, failed, args.output)
    print(json.dumps(report, indent=2))
    if args.report:
        args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
