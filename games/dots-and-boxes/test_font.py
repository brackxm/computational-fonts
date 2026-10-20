# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
from collections import Counter, deque
from functools import cache
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'shared'))
import exact_tests
import model


def edge(x, y, vertical):
    return frozenset(((x, y), (x, y+1) if vertical else (x+1, y)))


EDGES = {f'{chr(65+x)}{y+1}{direction};': edge(x, y, direction == 'V')
         for y in range(3) for x in range(3) for direction in 'HV'
         if (direction == 'H' and x < 2) or (direction == 'V' and y < 2)}
BOXES = tuple(frozenset((edge(x, y, False), edge(x, y+1, False), edge(x, y, True), edge(x+1, y, True)))
              for y in range(2) for x in range(2))


@cache
def closed(occupied):
    return frozenset(i for i, edges in enumerate(BOXES) if edges <= occupied)


@cache
def reference(occupied):
    """Future score advantage for the player to move; no ownership or turn table."""
    values = []
    for e in EDGES.values():
        if e in occupied:
            continue
        child = occupied | {e}
        gained = len(closed(child)-closed(occupied))
        values.append(gained+(reference(child) if gained else -reference(child)))
    return max(values, default=0)


def occupied_edges(mask):
    # Decode the model's numbered tape separately into geometric edge pairs.
    horizontal = {edge(i%2, i//2, False) for i in range(6) if mask & (1 << i)}
    vertical = {edge(i%3, i//3, True) for i in range(6) if mask & (1 << (6+i))}
    return frozenset(horizontal | vertical)


class DotsAndBoxesTests(exact_tests.ExactFontTests):
    rules = model
    font = Path(__file__).with_name('dots-and-boxes-font.ttf')

    def test_independent_geometric_score_solver(self):
        self.assertEqual(len(self.policy.nodes), 5559)
        self.assertEqual(model.margin(model.INITIAL), 2)
        relative = Counter(0 if w == 2 else 1 if w == n[1] else -1 for n, w in self.policy.outcomes.items())
        self.assertEqual(relative, {1: 3123, -1: 869, 0: 1567})
        for node, options in self.policy.graph.items():
            (mask, owners), side = node
            occupied = occupied_edges(mask)
            self.assertEqual({i for i, owner in enumerate(owners) if owner != -1}, closed(occupied))
            margin = owners.count(0)-owners.count(1)+(1 if side == 0 else -1)*reference(occupied)
            self.assertEqual(model.margin(node), margin)
            self.assertEqual(self.policy.solve(node)[0], 2 if margin == 0 else 0 if margin > 0 else 1)
            self.assertEqual(set(options), {token for token, e in EDGES.items() if e not in occupied})
            for token, child in options.items():
                after = occupied | {EDGES[token]}
                captured = closed(after)-closed(occupied)
                expected_owners = tuple(side if i in captured else owner for i, owner in enumerate(owners))
                self.assertEqual(occupied_edges(child[0][0]), after)
                self.assertEqual(child[0][1], expected_owners)
                self.assertEqual(child[1], side if captured else 1-side)
            if options:
                self.assertEqual(model.margin(options[self.policy.choose(node)]), margin)

    def test_bonus_turns_and_double_boxes(self):
        captures = Counter()
        for node, options in self.policy.graph.items():
            before = node[0][1].count(-1)
            for child in options.values():
                captures[before-child[0][1].count(-1)] += 1
        self.assertGreater(captures[1], 0)
        self.assertGreater(captures[2], 0)
        found = set()
        pending, seen = deque(['h', 'b']), set()
        while pending:
            source = pending.popleft()
            node, last, status = self.policy.replay(source)
            if status != 'ready' or node in seen:
                continue
            seen.add(node)
            for token in self.policy.graph[node]:
                candidate = source+token
                child, move, result = self.policy.replay(candidate)
                drawn = child[0][0].bit_count()-node[0][0].bit_count()
                if drawn == 1 and result == 'ready':
                    self.check_source(candidate)
                    self.assertEqual(move, last)
                    found.add('human_bonus')
                elif drawn > 2:
                    self.check_source(candidate)
                    found.add('font_chain')
                pending.append(candidate)
        self.assertEqual(found, {'human_bonus', 'font_chain'})


if __name__ == '__main__':
    unittest.main()
