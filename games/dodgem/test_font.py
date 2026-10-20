# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'shared'))
import exact_tests
from exactgame import Policy
import model


def reference_moves(node):
    blue, red, side = node
    own, enemy = (blue, red) if side == 0 else (red, blue)
    result = {}
    for i in range(9):
        if not own & (1 << i):
            continue
        for j in range(9):
            if (own | enemy) & (1 << j):
                continue
            legal = (j == i+1 and i%3 < 2) or (abs(j-i) == 3)
            if side == 1:
                legal = (j == i+3) or (abs(j-i) == 1 and j//3 == i//3)
            if not legal:
                continue
            changed = own ^ (1 << i) ^ (1 << j)
            result[model.square(i)+model.square(j)+';'] = ((changed, enemy, 1) if side == 0 else (enemy, changed, 0))
        if (side == 0 and i%3 == 2) or (side == 1 and i >= 6):
            changed = own ^ (1 << i)
            result[model.square(i)+'X;'] = ((changed, enemy, 1) if side == 0 else (enemy, changed, 0))
    return result


def bits(node):
    board, side = node
    return tuple(sum(1 << i for i, c in enumerate(board) if c == str(s)) for s in (0, 1))+(side,)


def reference_winner(node):
    if not node[0]:
        return 0
    if not node[1]:
        return 1
    return 1-node[2] if not reference_moves(node) else None


class DodgemTests(exact_tests.ExactFontTests):
    rules = model
    font = Path(__file__).with_name('dodgem-font.ttf')

    def test_cycle_attractors(self):
        a, b, c, d, end = ('a', 0), ('b', 1), ('c', 0), ('d', 1), ('end', 0)
        edges = {a: {'B;': b, 'C;': c, 'E;': end}, b: {'A;': a},
                 c: {'D;': d}, d: {'C;': c}, end: {}}
        rules = SimpleNamespace(INITIAL=a, moves=edges.__getitem__, winner=lambda n: 0 if n == end else None)
        policy = Policy(rules)
        self.assertEqual(policy.solve(a), (0, 1))
        self.assertEqual(policy.solve(b), (0, 2))
        self.assertEqual(policy.solve(c), (2, None))
        self.assertEqual(policy.solve(d), (2, None))
        self.assertEqual(policy.choose(a), 'E;')

    def test_independent_graph_and_fixed_point(self):
        graph, pending = {}, [bits(model.INITIAL)]
        while pending:
            node = pending.pop()
            if node in graph:
                continue
            graph[node] = {} if reference_winner(node) is not None else reference_moves(node)
            pending.extend(graph[node].values())
        self.assertEqual(set(graph), {bits(n) for n in self.policy.nodes})
        self.assertEqual(len(graph), 1963)
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
        self.assertEqual(self.policy.solve(model.INITIAL), (0, 19))


if __name__ == '__main__':
    unittest.main()
