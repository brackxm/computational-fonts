# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
from functools import cache
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'shared'))
import exact_tests
import model


@cache
def grundy(n):
    options = {grundy(left) ^ grundy(n-count-left)
               for count in (1, 2) for left in range(n-count+1)}
    value = 0
    while value in options:
        value += 1
    return value


class KaylesTests(exact_tests.ExactFontTests):
    rules = model
    font = Path(__file__).with_name('kayles-font.ttf')

    def test_independent_run_nim_values(self):
        masks = set()
        for node, options in self.policy.graph.items():
            mask, side = node
            standing = {i for i in range(12) if mask & (1 << i)}
            expected = {}
            for i in standing:
                expected[f'{i+1:02}S;'] = sum(1 << j for j in standing-{i})
                if i+1 in standing:
                    expected[f'{i+1:02}D;'] = sum(1 << j for j in standing-{i, i+1})
            self.assertEqual({t: c[0] for t, c in options.items()}, expected)
            nim, run = 0, 0
            for i in range(13):
                if i in standing:
                    run += 1
                else:
                    nim ^= grundy(run)
                    run = 0
            self.assertEqual(self.policy.solve(node)[0], side if nim else 1-side)
            masks.add(mask)
        self.assertEqual(len(masks), 4096)
        self.assertEqual(self.policy.solve(model.INITIAL)[0], 0)
        # A gap does not create a newly adjacent pair.
        self.assertNotIn('01D;', model.moves((5, 0)))


if __name__ == '__main__':
    unittest.main()
