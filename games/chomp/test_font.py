# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
from functools import cache
from itertools import combinations_with_replacement
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'shared'))
import exact_tests
from exactgame import Policy
import model


class ChompTests(exact_tests.ExactFontTests):
    rules = model
    font = Path(__file__).with_name('chomp-font.ttf')

    def test_independent_bitboard_solver(self):
        def mask(rows):
            return sum(((1 << length)-1) << (6*y) for y, length in enumerate(rows))
        bites = {f'{chr(65+x)}{y+1};': sum(1 << (6*j+i) for j in range(y, 5) for i in range(x, 6))
                 for y in range(5) for x in range(6) if (x, y) != (0, 0)}
        @cache
        def solve(board):
            children = [solve(board & ~bite) for token, bite in bites.items()
                        if board & (1 << (6*(int(token[1])-1)+ord(token[0])-65))]
            if not children:
                return -1, 0
            wins = [d for v, d in children if v == -1]
            return (1, 1+min(wins)) if wins else (-1, 1+max(d for _, d in children))
        shapes = {tuple(reversed(row)) for row in combinations_with_replacement(range(7), 5) if row[-1]}
        self.assertEqual(len(shapes), 461)
        self.assertEqual({node[0] for node in self.policy.nodes}, shapes)
        for node, options in self.policy.graph.items():
            rows, side = node
            board = mask(rows)
            expected = {token: board & ~bite for token, bite in bites.items()
                        if board & (1 << (6*(int(token[1])-1)+ord(token[0])-65))}
            self.assertEqual({token: mask(child[0]) for token, child in options.items()}, expected)
            winner, distance = self.policy.solve(node)
            self.assertEqual((1 if winner == side else -1, distance), solve(board))
        self.assertEqual(self.policy.solve(model.INITIAL)[0], 0)


if __name__ == '__main__':
    unittest.main()
