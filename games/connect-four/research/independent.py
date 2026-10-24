# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Independent Connect Four research: no production or upstream game imports.

The only inputs are the rules, an optional legal move sequence and explicit
resource limits. This is not a replacement for the published winning policy.
Columns are 1-based in serialized data, 0-based in Python.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import random
import sys
import time

WIDTH, HEIGHT, STRIDE = 7, 6, 7
ORDER = (3, 2, 4, 1, 5, 0, 6)
MASKS = tuple(((1 << HEIGHT) - 1) << (STRIDE * c) for c in range(WIDTH))
FULL = sum(MASKS)


def four(discs):
    for shift in (1, STRIDE, STRIDE - 1, STRIDE + 1):
        pairs = discs & (discs >> shift)
        if pairs & (pairs >> (2 * shift)):
            return True
    return False


def legal(red, yellow):
    occupied = red | yellow
    return tuple(c for c in range(WIDTH) if not occupied & (1 << (STRIDE*c+HEIGHT-1)))


def place(red, yellow, col, player):
    if not 0 <= col < WIDTH:
        raise ValueError('column outside 1..7')
    occupied = red | yellow
    column = (occupied >> (STRIDE*col)) & ((1 << HEIGHT)-1)
    if column == (1 << HEIGHT)-1:
        raise ValueError('full column')
    bit = 1 << (STRIDE*col + column.bit_count())
    return (red | bit, yellow) if player == 1 else (red, yellow | bit)


def parse(history):
    red = yellow = 0
    for ply, char in enumerate(history):
        if char not in '1234567' or four(red) or four(yellow):
            raise ValueError('malformed history or moves after a win')
        red, yellow = place(red, yellow, int(char)-1, 1+ply%2)
    return red, yellow, 1+len(history)%2


def wins(red, yellow, player):
    return tuple(c for c in legal(red, yellow)
                 if four(place(red, yellow, c, player)[player-1]))


def mirror(bits):
    return sum(((bits & MASKS[c]) >> (STRIDE*c)) << (STRIDE*(WIDTH-1-c))
               for c in range(WIDTH))


def canonical(red, yellow, player):
    return min((red, yellow, player), (mirror(red), mirror(yellow), player))


class BudgetExceeded(Exception):
    pass


class Exact:
    """AND/OR proof search for a strict Red win; draws are failures.

    Unknown on budget exhaustion is never cached as a win or a loss. A true
    value is a proof for the position, not a guarantee of a small font policy.
    """
    def __init__(self, budget):
        self.budget, self.nodes, self.memo = budget, 0, {}

    def solve(self, red, yellow, player):
        if four(red):
            return True
        if four(yellow) or red | yellow == FULL:
            return False
        key = canonical(red, yellow, player)
        if key in self.memo:
            return self.memo[key]
        if self.nodes >= self.budget:
            raise BudgetExceeded
        self.nodes += 1
        own = wins(red, yellow, player)
        threats = wins(red, yellow, 3-player)
        if own:
            result = player == 1
        elif len(threats) > 1:
            result = player == 2
        else:
            choices = threats or tuple(c for c in ORDER if c in legal(red, yellow))
            if player == 1:
                result = any(self.solve(*place(red, yellow, c, player), 2) for c in choices)
            else:
                result = all(self.solve(*place(red, yellow, c, player), 1) for c in choices)
        self.memo[key] = result
        return result

    def certificate(self, red, yellow, player, choose=None):
        """Extract a closed policy DAG, expanding shortcuts into actual moves."""
        if not self.solve(red, yellow, player):
            raise ValueError('no strict Red win from this position')
        nodes = {}

        def visit(red, yellow, player):
            key = state_key(red, yellow, player)
            if key in nodes:
                return key
            if four(red):
                nodes[key] = {'terminal': 'red'}
                return key
            if four(yellow) or red | yellow == FULL:
                raise ValueError('certificate reached a loss or draw')
            choices = tuple(c for c in ORDER if c in legal(red, yellow))
            if player == 1:
                if choose is not None:
                    chosen = choose(red, yellow)
                    if chosen not in choices or not self.solve(*place(red, yellow, chosen, 1), 2):
                        raise ValueError('supplied policy does not preserve the strict win')
                    choices = (chosen,)
                else:
                    choices = (next(c for c in choices
                                    if self.solve(*place(red, yellow, c, 1), 2)),)
            nodes[key] = {'edges': {str(c+1): visit(*place(red, yellow, c, player), 3-player)
                                    for c in choices}}
            return key

        root = visit(red, yellow, player)
        return {'format': 'independent-c4-policy-v1', 'root': root, 'nodes': nodes}


def state_key(red, yellow, player):
    return f'{red:x}/{yellow:x}/{player}'


def array_board(red, yellow):
    return [[1 if red & (1 << (STRIDE*c+r)) else
             2 if yellow & (1 << (STRIDE*c+r)) else 0
             for c in range(WIDTH)] for r in range(HEIGHT)]


ARRAY_LINES = [tuple((r+i*dr, c+i*dc) for i in range(4))
               for r in range(HEIGHT) for c in range(WIDTH)
               for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1))
               if 0 <= r+3*dr < HEIGHT and 0 <= c+3*dc < WIDTH]


def array_won(board, player):
    """Separate coordinate-based win detector for certificate checking."""
    return any(all(board[r][c] == player for r, c in line) for line in ARRAY_LINES)


def check_certificate(certificate, history):
    """Replay every edge with array mechanics, without trusting solver values.

    The starting position must match a legal history. Every Yellow move is
    required, every Red node has exactly one move, and only Red wins terminate.
    """
    board = [[0]*WIDTH for _ in range(HEIGHT)]

    def drop(board, col, player):
        row = next((r for r in range(HEIGHT) if board[r][col] == 0), None)
        if row is None:
            raise ValueError('certificate move into full column')
        after = [line[:] for line in board]
        after[row][col] = player
        return after

    for ply, char in enumerate(history):
        if char not in '1234567' or array_won(board, 1) or array_won(board, 2):
            raise ValueError('illegal root history')
        board = drop(board, int(char)-1, 1+ply%2)

    def key_of(board, player):
        bits = [0, 0]
        for r in range(HEIGHT):
            for c in range(WIDTH):
                if board[r][c]:
                    bits[board[r][c]-1] |= 1 << (STRIDE*c+r)
        return state_key(*bits, player)

    if certificate.get('format') != 'independent-c4-policy-v1':
        raise ValueError('unsupported certificate')
    nodes, visited = certificate['nodes'], set()

    def visit(key, board, player):
        if key != key_of(board, player):
            raise ValueError('board/edge mismatch')
        if key in visited:
            return
        node = nodes[key]
        if array_won(board, 2):
            raise ValueError('Yellow wins')
        if array_won(board, 1):
            if node != {'terminal': 'red'}:
                raise ValueError('malformed terminal')
        else:
            available = {str(c+1) for c in range(WIDTH) if not board[HEIGHT-1][c]}
            edges = node.get('edges', {})
            if not available:
                raise ValueError('draw')
            if player == 2 and set(edges) != available:
                raise ValueError('missing or illegal Yellow reply')
            if player == 1 and (len(edges) != 1 or not set(edges) <= available):
                raise ValueError('Red must have one legal prescribed move')
            for char, child in edges.items():
                visit(child, drop(board, int(char)-1, player), 3-player)
        visited.add(key)

    visit(certificate['root'], board, 1+len(history)%2)
    if visited != set(nodes):
        raise ValueError('unreachable certificate nodes')
    return {'nodes': len(visited), 'edges': sum(len(v.get('edges', {})) for v in nodes.values()),
            'red_nodes': sum(key.endswith('/1') and 'edges' in node for key, node in nodes.items()),
            'yellow_nodes': sum(key.endswith('/2') and 'edges' in node for key, node in nodes.items()),
            'terminal_nodes': sum('terminal' in node for node in nodes.values())}


def tactical(red, yellow, order=ORDER):
    for player in (1, 2):
        winning = wins(red, yellow, player)
        if winning:
            return next(c for c in order if c in winning)
    return next(c for c in order if c in legal(red, yellow))


def refute_policy(choose, budget, history):
    """Return a losing/drawing human continuation, or None after full coverage."""
    visited, nodes = set(), 0

    def visit(red, yellow):
        nonlocal nodes
        if four(red):
            return None
        if four(yellow) or red | yellow == FULL:
            return ''
        key = (red, yellow)
        if key in visited:
            return None
        if nodes >= budget:
            raise BudgetExceeded
        nodes += 1
        for col in ORDER:
            if col not in legal(red, yellow):
                continue
            r, y = place(red, yellow, col, 2)
            if four(y) or r | y == FULL:
                return str(col+1)
            r, y = place(r, y, choose(r, y), 1)
            suffix = visit(r, y)
            if suffix is not None:
                return str(col+1)+suffix
        visited.add(key)
        return None

    red, yellow, player = parse(history)
    if player != 2:
        raise ValueError('fixed policy check requires a Yellow-to-move root')
    return visit(red, yellow), nodes


def refute_tactical(order, budget, history='4'):
    """Find one legal human history beating the fixed win/block/order policy."""
    return refute_policy(lambda r, y: tactical(r, y, order), budget, history)


def landing(red, yellow, col):
    return HEIGHT*col + (((red | yellow) >> (STRIDE*col)) & ((1 << HEIGHT)-1)).bit_count()


def ranked(red, yellow, priorities):
    """Win, block, then the lowest-ranked playable cell; all ranks are unique."""
    for player in (1, 2):
        winning = wins(red, yellow, player)
        if winning:
            return next(c for c in ORDER if c in winning)
    return min(legal(red, yellow), key=lambda c: priorities[landing(red, yellow, c)])


def rank_constraints(constraints):
    """Solve min(good) < min(bad) constraints by monotone elimination.

    A cell is eligible for the next rank iff it is not a bad choice in any
    unsatisfied constraint. Selecting a good cell satisfies that constraint.
    Selection can only unlock cells. No eligible cell therefore proves this
    constraint set cannot be represented by a single strict cell ordering.
    """
    remaining = [HEIGHT*c+r for c in ORDER for r in range(HEIGHT)]
    pending = list(constraints)
    result = [None]*(WIDTH*HEIGHT)
    for priority in range(WIDTH*HEIGHT):
        blocked = set().union(*(bad for good, bad in pending))
        cell = next((cell for cell in remaining if cell not in blocked), None)
        if cell is None:
            return None
        result[cell] = priority
        remaining.remove(cell)
        pending = [(good, bad) for good, bad in pending if cell not in good]
    return result


def synthesize_cells(history, budget=1000000, iterations=200):
    """Discover an original cell ordering from exact-oracle counterexamples.

    No imported diagrams, solution graph, solver cache or policy labels.
    This is a different language from tie-cancelling multi-level diagrams:
    every square has a unique rank and ties are impossible.
    """
    engine, constraints, examples = Exact(budget), [], []
    try:
        if not engine.solve(*parse(history)):
            return {'status': 'not_a_strict_red_win', 'oracle_nodes': engine.nodes}
        for iteration in range(iterations):
            priorities = rank_constraints(constraints)
            if priorities is None:
                return {'status': 'policy_language_unsatisfiable',
                        'constraints': len(constraints), 'oracle_nodes': engine.nodes}
            witness, verified_nodes = refute_policy(lambda r, y: ranked(r, y, priorities), budget, history)
            if witness is None:
                certificate = engine.certificate(*parse(history), choose=lambda r, y: ranked(r, y, priorities))
                return {'status': 'verified', 'priorities_column_major_bottom_up': priorities,
                        'constraints': len(constraints), 'iterations': iteration+1,
                        'verification_nodes': verified_nodes, 'oracle_nodes': engine.nodes,
                        'independently_checked_certificate': check_certificate(certificate, history),
                        'examples': examples}
            red, yellow, _ = parse(history)
            for human in witness:
                red, yellow = place(red, yellow, int(human)-1, 2)
                if four(yellow) or red | yellow == FULL:
                    raise AssertionError('winning oracle admitted an immediate loss/draw')
                chosen = ranked(red, yellow, priorities)
                if not engine.solve(*place(red, yellow, chosen, 1), 2):
                    good_cols = [c for c in legal(red, yellow)
                                 if engine.solve(*place(red, yellow, c, 1), 2)]
                    if not good_cols:
                        raise AssertionError('oracle inconsistency')
                    good = {landing(red, yellow, c) for c in good_cols}
                    bad = {landing(red, yellow, c) for c in legal(red, yellow) if c not in good_cols}
                    constraints.append((good, bad))
                    examples.append({'board': state_key(red, yellow, 1),
                                     'allowed_columns': [c+1 for c in good_cols]})
                    break
                red, yellow = place(red, yellow, chosen, 1)
            else:
                raise AssertionError('counterexample contains no losing Red decision')
        return {'status': 'unknown_iteration_limit', 'constraints': len(constraints),
                'oracle_nodes': engine.nodes}
    except BudgetExceeded:
        return {'status': 'unknown_budget_exceeded', 'constraints': len(constraints),
                'oracle_nodes': engine.nodes}


def tactical_survives(order, history, human):
    """Whether an earlier counterexample fails to refute this candidate order."""
    red, yellow, _ = parse(history)
    for char in human:
        if four(red):
            return True
        if four(yellow) or red | yellow == FULL:
            return False
        col = int(char)-1
        if col not in legal(red, yellow):
            return True  # This candidate makes the old history illegal.
        red, yellow = place(red, yellow, col, 2)
        if four(yellow) or red | yellow == FULL:
            return False
        red, yellow = place(red, yellow, tactical(red, yellow, order), 1)
    return four(red) or (not four(yellow) and red | yellow != FULL)


def synthesize_order(history):
    """Finite counterexample-guided synthesis of win/block/column-order leaves.

    This policy language is deliberately simpler than per-cell priority maps.
    Only a completed exhaustive search accepts a leaf; a budget limit cannot.
    """
    counterexamples, unknown = [], 0
    verifications = search_nodes = filtered = 0
    for order in itertools.permutations(ORDER):
        if any(not tactical_survives(order, history, witness) for witness in counterexamples):
            filtered += 1
            continue
        verifications += 1
        try:
            witness, nodes = refute_tactical(order, 100000, history)
            search_nodes += nodes
        except BudgetExceeded:
            unknown += 1
            continue
        if witness is None:
            return {'order': ''.join(str(c+1) for c in order),
                    'exhaustively_verified': True, 'verifications': verifications,
                    'filtered_candidates': filtered, 'counterexamples': len(counterexamples),
                    'search_nodes': search_nodes, 'unknown_candidates': unknown}
        counterexamples.append(witness)
    return {'order': None, 'exhaustively_verified': False, 'verifications': verifications,
            'filtered_candidates': filtered, 'counterexamples': len(counterexamples),
            'search_nodes': search_nodes, 'unknown_candidates': unknown}


def sample_position(seed, plies):
    """Seeded legal nonterminal history generated without any strategy book."""
    rng = random.Random(seed)
    for _ in range(10000):
        history, red, yellow = '', 0, 0
        for ply in range(plies):
            choices = [c for c in legal(red, yellow)
                       if not four(place(red, yellow, c, 1+ply%2)[ply%2])]
            if not choices:
                break
            col = rng.choice(choices)
            red, yellow = place(red, yellow, col, 1+ply%2)
            history += str(col+1)
        if len(history) == plies and not wins(red, yellow, 1) and not wins(red, yellow, 2):
            return history
    raise RuntimeError('could not sample a nonterminal position')


def run_experiments(output):
    started = time.perf_counter()
    results = {'format': 'independent-c4-research-v1',
               'complete_empty_board_replacement': False,
               'python': sys.version, 'endgames': []}
    for plies in (23, 27, 31):
        for seed in range(5):
            history = sample_position(seed, plies)
            engine = Exact(250000)
            entry = {'history': history, 'plies': plies, 'seed': seed}
            begin = time.perf_counter()
            try:
                winner = engine.solve(*parse(history))
                entry['strict_red_win'] = winner
                if winner:
                    certificate = engine.certificate(*parse(history))
                    entry['certificate'] = check_certificate(certificate, history)
                    entry['certificate_json_bytes'] = len(json.dumps(certificate, separators=(',', ':')))
                    entry['synthesized_column_policy'] = synthesize_order(history)
                    entry['synthesized_cell_policy'] = synthesize_cells(history)
            except BudgetExceeded:
                entry['unknown_budget_exceeded'] = True
            entry.update(search_nodes=engine.nodes, seconds=round(time.perf_counter()-begin, 4))
            results['endgames'].append(entry)
    engine = Exact(250000)
    begin = time.perf_counter()
    try:
        root = {'strict_red_win': engine.solve(0, 0, 1)}
    except BudgetExceeded:
        root = {'unknown_budget_exceeded': True}
    root.update(search_nodes=engine.nodes, seconds=round(time.perf_counter()-begin, 4))
    results['empty_board'] = root
    witnesses, unresolved = [], []
    for order in itertools.permutations(range(WIDTH)):
        try:
            witness, nodes = refute_tactical(order, 10000)
            if witness is None:
                unresolved.append(''.join(str(c+1) for c in order))
            else:
                witnesses.append({'order': ''.join(str(c+1) for c in order),
                                  'human': witness, 'nodes': nodes})
        except BudgetExceeded:
            unresolved.append(''.join(str(c+1) for c in order))
    witness_path = output.with_name('tactical-witnesses.json.gz')
    witness_bytes = gzip.compress(json.dumps(witnesses, separators=(',', ':')).encode(), mtime=0)
    witness_path.write_bytes(witness_bytes)
    results['tactical_orders'] = {'tested': 5040, 'refuted': len(witnesses),
                                  'unresolved': unresolved, 'witnesses_file': witness_path.name,
                                  'witnesses_sha256': hashlib.sha256(witness_bytes).hexdigest()}
    results['seconds'] = round(time.perf_counter()-started, 4)
    output.write_text(json.dumps(results, indent=2)+'\n')
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiments', type=Path)
    parser.add_argument('--history')
    parser.add_argument('--certificate', type=Path)
    parser.add_argument('--budget', type=int, default=250000)
    args = parser.parse_args()
    if args.experiments:
        result = run_experiments(args.experiments)
        print(json.dumps({key: value for key, value in result.items() if key != 'tactical_orders'}, indent=2))
        print('Tactical orders:', {k: v for k, v in result['tactical_orders'].items() if k != 'witnesses'})
    elif args.history is not None:
        engine = Exact(args.budget)
        try:
            result = engine.solve(*parse(args.history))
            print(json.dumps({'strict_red_win': result, 'search_nodes': engine.nodes}))
            if result and args.certificate:
                certificate = engine.certificate(*parse(args.history))
                print(json.dumps(check_certificate(certificate, args.history)))
                args.certificate.write_text(json.dumps(certificate, indent=2)+'\n')
        except BudgetExceeded:
            print(json.dumps({'unknown_budget_exceeded': True, 'search_nodes': engine.nodes}))
            raise SystemExit(2)
    else:
        parser.error('provide --experiments or --history')


if __name__ == '__main__':
    main()
