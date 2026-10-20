# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
from collections import Counter
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'shared'))
import exact_tests
import model

ADJACENT = ((1, 3, 4), (0, 2, 4), (1, 4, 5), (0, 4, 6), (0, 1, 2, 3, 5, 6, 7, 8),
            (2, 4, 8), (3, 4, 7), (4, 6, 8), (4, 5, 7))
LINES = (7, 56, 448, 73, 146, 292, 273, 84)


def bits(node):
    return tuple(sum(1 << i for i, c in enumerate(node[0]) if c == str(s)) for s in (0, 1))+(node[1],)


def reference_moves(node):
    a, b, side = node
    own, enemy = (a, b) if side == 0 else (b, a)
    result = {}
    for target in range(9):
        if (own | enemy) & (1 << target):
            continue
        origins = [None] if own.bit_count() < 3 else [i for i in range(9) if own & (1 << i) and target in ADJACENT[i]]
        for origin in origins:
            changed = (own | (1 << target)) if origin is None else own ^ (1 << origin) ^ (1 << target)
            token = ('' if origin is None else model.square(origin))+model.square(target)+';'
            result[token] = (changed, enemy, 1) if side == 0 else (enemy, changed, 0)
    return result


def reference_winner(node):
    for side in (0, 1):
        if any(node[side] & line == line for line in LINES):
            return side
    return 1-node[2] if not reference_moves(node) else None


class AchiTests(exact_tests.ExactFontTests):
    rules = model
    font = Path(__file__).with_name('achi-font.ttf')

    def test_independent_bitboards_and_draw_fixed_point(self):
        graph, pending = {}, [(0, 0, 0)]
        while pending:
            node = pending.pop()
            if node in graph:
                continue
            graph[node] = {} if reference_winner(node) is not None else reference_moves(node)
            pending.extend(graph[node].values())
        self.assertEqual(set(graph), {bits(n) for n in self.policy.nodes})
        self.assertEqual(len(graph), 5390)
        values = {n: reference_winner(n) for n in graph if reference_winner(n) is not None}
        while True:
            added = {}
            for node, options in graph.items():
                if node in values:
                    continue
                if any(values.get(c) == node[2] for c in options.values()):
                    added[node] = node[2]
                elif all(values.get(c) == 1-node[2] for c in options.values()):
                    added[node] = 1-node[2]
            if not added:
                break
            values.update(added)
        for node in self.policy.nodes:
            ref = bits(node)
            self.assertEqual(model.winner(node), reference_winner(ref))
            self.assertEqual({t: bits(c) for t, c in self.policy.graph[node].items()}, graph[ref])
            self.assertEqual(self.policy.solve(node)[0], values.get(ref, 2))
        relative = Counter(0 if w == 2 else 1 if w == n[1] else -1 for n, w in self.policy.outcomes.items())
        self.assertEqual(relative, {1: 2997, -1: 1185, 0: 1208})
        self.assertEqual(self.policy.solve(model.INITIAL), (0, 9))

    def test_draw_offers(self):
        for source in ('h=', 'hA1;=', 'b=', 'hA1;=ignored🙂'):
            self.check_source(source)
        self.assertEqual(self.policy.replay('hA1;=')[2], 'draw')
        self.assertEqual(self.policy.replay('b=')[2], 'invalid')


if __name__ == '__main__':
    unittest.main()
