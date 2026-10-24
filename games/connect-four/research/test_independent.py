# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Tests for the independent research code, never the GPL production policy."""
from copy import deepcopy
from functools import lru_cache
import gzip
import itertools
import json
from pathlib import Path
import random
import unittest

import independent as c

HERE = Path(__file__).resolve().parent
ROOT = '77111372676733526176246'


def drop(board, col, player):
    after = [list(row) for row in board]
    row = next(r for r in range(6) if after[r][col] == 0)
    after[row][col] = player
    return tuple(map(tuple, after))


@lru_cache(None)
def brute(board, player):
    if c.array_won(board, 1):
        return True
    if c.array_won(board, 2):
        return False
    choices = [col for col in range(7) if not board[5][col]]
    if not choices:
        return False
    values = (brute(drop(board, col, player), 3-player) for col in choices)
    return any(values) if player == 1 else all(values)


class IndependentTests(unittest.TestCase):
    def test_coordinate_and_bitboard_rules_agree(self):
        rng = random.Random(3)
        for _ in range(100):
            red = yellow = 0
            board = tuple((0,)*7 for _ in range(6))
            for ply in range(42):
                legal = c.legal(red, yellow)
                self.assertEqual(legal, tuple(col for col in range(7) if not board[5][col]))
                self.assertEqual(c.four(red), c.array_won(board, 1))
                self.assertEqual(c.four(yellow), c.array_won(board, 2))
                if c.four(red) or c.four(yellow) or not legal:
                    break
                col = rng.choice(legal)
                red, yellow = c.place(red, yellow, col, 1+ply%2)
                board = drop(board, col, 1+ply%2)
                self.assertEqual(c.array_board(red, yellow), list(map(list, board)))

    def test_exact_matches_unpruned_array_minimax(self):
        for seed in range(20):
            history = c.sample_position(seed, 35)
            red, yellow, player = c.parse(history)
            board = tuple(map(tuple, c.array_board(red, yellow)))
            self.assertEqual(c.Exact(100000).solve(red, yellow, player), brute(board, player), history)
        draw = c.sample_position(5, 42)
        self.assertFalse(c.Exact(0).solve(*c.parse(draw)))

    def test_budget_is_unknown(self):
        engine = c.Exact(10)
        with self.assertRaises(c.BudgetExceeded):
            engine.solve(0, 0, 1)
        self.assertNotIn(c.canonical(0, 0, 1), engine.memo)

    def test_certificate_rejects_missing_reply_and_wrong_board(self):
        certificate = c.Exact(100000).certificate(*c.parse(ROOT))
        self.assertGreater(c.check_certificate(certificate, ROOT)['nodes'], 1000)
        broken = deepcopy(certificate)
        broken['nodes'][broken['root']]['edges'].popitem()
        with self.assertRaisesRegex(ValueError, 'missing or illegal Yellow'):
            c.check_certificate(broken, ROOT)
        broken = deepcopy(certificate)
        root = broken['nodes'][broken['root']]['edges']
        root[next(iter(root))] = broken['root']
        with self.assertRaisesRegex(ValueError, 'board/edge mismatch'):
            c.check_certificate(broken, ROOT)
        broken = deepcopy(certificate)
        terminal = next(key for key, node in broken['nodes'].items() if 'terminal' in node)
        broken['nodes'][terminal]['terminal'] = 'yellow'
        with self.assertRaisesRegex(ValueError, 'malformed terminal'):
            c.check_certificate(broken, ROOT)

    def test_rank_constraint_solver_against_all_three_cell_orders(self):
        constraints = []
        for labels in itertools.product(range(3), repeat=3):
            good = {i for i, label in enumerate(labels) if label == 1}
            bad = {i for i, label in enumerate(labels) if label == 2}
            if good and bad:
                constraints.append((good, bad))
        for case in itertools.product(constraints, repeat=2):
            possible = any(all(min(order.index(g) for g in good) < min(order.index(b) for b in bad)
                               for good, bad in case)
                           for order in itertools.permutations(range(3)))
            ranks = c.rank_constraints(case)
            self.assertEqual(ranks is not None, possible)
            if ranks is not None:
                self.assertEqual(set(ranks), set(range(42)))
                self.assertTrue(all(min(ranks[g] for g in good) < min(ranks[b] for b in bad)
                                    for good, bad in case))

    def test_synthesized_policy_has_independently_checked_proof(self):
        result = c.synthesize_cells(ROOT)
        self.assertEqual(result['status'], 'verified')
        self.assertGreater(result['constraints'], 0)
        self.assertGreater(result['independently_checked_certificate']['yellow_nodes'], 20)
        ranks = result['priorities_column_major_bottom_up']
        witness, _ = c.refute_policy(lambda r, y: c.ranked(r, y, ranks), 100000, ROOT)
        self.assertIsNone(witness)

    def test_all_5040_tactical_counterexamples_with_array_rules(self):
        with gzip.open(HERE/'tactical-witnesses.json.gz', 'rt') as source:
            witnesses = json.load(source)
        self.assertEqual(len(witnesses), 5040)
        self.assertEqual(len({w['order'] for w in witnesses}), 5040)
        for witness in witnesses:
            order = tuple(int(char)-1 for char in witness['order'])
            board = drop(tuple((0,)*7 for _ in range(6)), 3, 1)
            for i, human in enumerate(witness['human']):
                board = drop(board, int(human)-1, 2)
                if c.array_won(board, 2) or all(board[5]):
                    self.assertEqual(i, len(witness['human'])-1)
                    break
                chosen = None
                for player in (1, 2):
                    chosen = next((col for col in order if not board[5][col] and
                                   c.array_won(drop(board, col, player), player)), None)
                    if chosen is not None:
                        break
                if chosen is None:
                    chosen = next(col for col in order if not board[5][col])
                board = drop(board, chosen, 1)
                self.assertFalse(c.array_won(board, 1), witness)
            self.assertTrue(c.array_won(board, 2) or all(board[5]), witness)


if __name__ == '__main__':
    unittest.main()
