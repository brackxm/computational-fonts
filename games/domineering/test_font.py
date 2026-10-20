# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
from functools import cache
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'shared'))
import exact_tests
import model


def reference_moves(mask, side):
    cells = {(x, y) for y in range(4) for x in range(4) if mask & (1 << (4*y+x))}
    result = {}
    for y in range(4):
        for x in range(4):
            other = (x, y+1) if side == 0 else (x+1, y)
            if other[0] >= 4 or other[1] >= 4 or (x, y) in cells or other in cells:
                continue
            token = f'{chr(65+x)}{y+1}{"V" if side == 0 else "H"};'
            result[token] = mask | (1 << (4*y+x)) | (1 << (4*other[1]+other[0]))
    return result


@cache
def reference(mask, side):
    outcomes = [reference(child, 1-side) for child in reference_moves(mask, side).values()]
    if not outcomes:
        return -1, 0
    wins = [d for v, d in outcomes if v == -1]
    return (1, 1+min(wins)) if wins else (-1, 1+max(d for _, d in outcomes))


class DomineeringTests(exact_tests.ExactFontTests):
    rules = model
    font = Path(__file__).with_name('domineering-font.ttf')

    def test_independent_occupancy_solver(self):
        strategic = set()
        for node, options in self.policy.graph.items():
            (vertical, horizontal), side = node
            mask = vertical | horizontal
            self.assertFalse(vertical & horizontal)
            strategic.add((mask, side))
            expected = reference_moves(mask, side)
            self.assertEqual({t: c[0][0] | c[0][1] for t, c in options.items()}, expected)
            winner, distance = self.policy.solve(node)
            self.assertEqual((1 if winner == side else -1, distance), reference(mask, side))
        self.assertEqual(len(strategic), 2443)
        self.assertEqual(len(self.policy.nodes), 3120)
        self.assertEqual(self.policy.solve(model.INITIAL)[0], 0)


if __name__ == '__main__':
    unittest.main()
