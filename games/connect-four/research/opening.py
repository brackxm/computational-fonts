# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Persistent rule-only opening search, compact leaf synthesis and certificate.

The native oracle is only a generator aid. Acceptance requires the separate
hybrid certificate checker; neither an oracle value nor a partial frontier is
the distributed winning strategy.
"""
from __future__ import annotations

import argparse
from contextlib import AbstractContextManager
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import time

import independent as c


def normalized(red, yellow, player):
    direct, reflected = (red, yellow), (c.mirror(red), c.mirror(yellow))
    flip = reflected < direct
    red, yellow = reflected if flip else direct
    return (red, yellow, player), int(flip)


def decode(key):
    red, yellow, player = key.split('/')
    return int(red, 16), int(yellow, 16), int(player)


class Native(AbstractContextManager):
    def __init__(self, executable, cache_dir, budget=500000000, bits=25):
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.process = subprocess.Popen(
            [str(executable), '--table-bits', str(bits), '--budget', str(budget),
             '--cache', str(cache_dir/'oracle.bin')],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self.database = sqlite3.connect(cache_dir/'oracle.sqlite3')
        self.database.execute('CREATE TABLE IF NOT EXISTS answers (request TEXT PRIMARY KEY, response TEXT NOT NULL)')
        self.requests = self.nodes = 0
        self.started = time.monotonic()

    def query(self, request, cached=True):
        if cached:
            row = self.database.execute('SELECT response FROM answers WHERE request=?', (request,)).fetchone()
            if row:
                return json.loads(row[0])
        self.process.stdin.write(request+'\n')
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError(f'native oracle exited {self.process.poll()}')
        response = json.loads(line)
        if 'error' in response:
            raise ValueError(response['error'])
        self.nodes += response.get('nodes', 0)
        self.requests += 1
        if response.get('unknown_budget_exceeded'):
            return response
        if cached:
            self.database.execute('INSERT OR REPLACE INTO answers VALUES (?, ?)', (request, line))
            self.database.commit()
        return response

    def value(self, board):
        r, y, p = board
        request = f'bits {r:x} {y:x} {p}'
        while True:
            response = self.query(request)
            if 'strict_red_win' in response:
                return response['strict_red_win']
            print(json.dumps({'oracle_retry': c.state_key(*board), 'nodes': self.nodes}), flush=True)
            self.query('save', cached=False)

    def moves(self, board):
        r, y, p = board
        request = f'moves-bits {r:x} {y:x} {p}'
        while True:
            response = self.query(request)
            if 'winning_columns' in response:
                return [col-1 for col in response['winning_columns']]
            print(json.dumps({'oracle_retry_moves': c.state_key(*board), 'nodes': self.nodes}), flush=True)
            self.query('save', cached=False)

    def rank(self, board, ranks):
        r, y, p = board
        return self.query(f'rank {r:x} {y:x} {p} '+ ' '.join(map(str, ranks)))

    def levels(self, board, levels):
        r, y, p = board
        return self.query(f'levels {r:x} {y:x} {p} '+ ' '.join(map(str, levels)))

    def response(self, board, ranks):
        r, y, p = board
        return self.query(f'response {r:x} {y:x} {p} '+ ' '.join(str(x) for row in ranks for x in row))

    def __exit__(self, *args):
        if self.process.poll() is None:
            self.process.stdin.write('quit\n')
            self.process.stdin.flush()
            self.process.wait()
        self.database.close()


def synthesize(native, board, max_iterations=64):
    constraints = []
    for iteration in range(max_iterations):
        ranks = c.rank_constraints(constraints)
        if ranks is None:
            return None
        result = native.rank(board, ranks)
        if result.get('verified'):
            return {'ranks': ranks, 'verification_nodes': result['nodes'], 'iterations': iteration+1}
        if result.get('unknown_budget_exceeded'):
            return None
        red, yellow, player = board
        for move in result['witness']:
            col = int(move)-1
            if player == 1:
                after = (*c.place(red, yellow, col, 1), 2)
                if not native.value(after):
                    allowed = native.moves((red, yellow, 1))
                    if not allowed:
                        raise ValueError(f'non-winning synthesis root {c.state_key(*board)}')
                    good = {c.landing(red, yellow, x) for x in allowed}
                    bad = {c.landing(red, yellow, x) for x in c.legal(red, yellow) if x not in allowed}
                    constraints.append((good, bad))
                    break
            red, yellow = c.place(red, yellow, col, player)
            player = 3-player
        else:
            raise RuntimeError('counterexample with no losing Red decision')
    return None


def synthesize_sat(native, board, max_iterations=256):
    """True counterexample-guided synthesis of one strict cell ordering.

    A losing prefix forbids only the combination of rank choices that reaches
    it. Unlike unconditional training constraints, this preserves policies that
    avoid the troublesome position by making a different earlier Red move.
    """
    import z3
    base = c.rank_constraints([])
    values = [z3.Int(f'r{i}') for i in range(42)]
    solver = z3.SolverFor('QF_IDL')
    solver.set(timeout=5000)
    ranks = base

    def before(a, b):
        # Deterministic tie-breaking makes every integer model a strict order,
        # without the expensive global AllDifferent constraint.
        return values[a] <= values[b] if base[a] < base[b] else values[a] < values[b]

    for iteration in range(max_iterations):
        result = native.rank(board, ranks)
        if result.get('verified'):
            return {'ranks': ranks, 'verification_nodes': result['nodes'],
                    'iterations': iteration+1, 'synthesis': 'conditional-prefix-smt'}
        if result.get('unknown_budget_exceeded'):
            return None
        red, yellow, player = board
        alternatives = []
        for move in result['witness']:
            col = int(move)-1
            if player == 1:
                if not c.wins(red, yellow, 1) and not c.wins(red, yellow, 2):
                    selected = c.landing(red, yellow, col)
                    alternatives += [before(c.landing(red, yellow, x), selected)
                                     for x in c.legal(red, yellow) if x != col]
                if not native.value((*c.place(red, yellow, col, 1), 2)):
                    break
            red, yellow = c.place(red, yellow, col, player)
            player = 3-player
        solver.add(z3.Or(alternatives))
        if solver.check() != z3.sat:
            return None
        model = solver.model()
        cells = sorted(range(42), key=lambda i: (model.eval(values[i], model_completion=True).as_long(), base[i]))
        ranks = [0]*42
        for rank, cell in enumerate(cells):
            ranks[cell] = rank
    return None


def synthesize_levels(native, board, max_iterations=128):
    """Generate new tie-cancelling priorities, checked over all continuations.

    The language is an abstract numerical policy, not copied implementation or
    data. Constraints here are deliberately stronger than necessary: failure
    expands the opening graph and is never treated as a game-theoretic loss.
    """
    import z3
    values = [z3.BitVec(f'p{i}', 4) for i in range(42)]
    solver = z3.SolverFor('QF_BV')
    solver.set(timeout=3000)
    solver.add(*[z3.ULE(value, 9) for value in values])
    levels = [c.ORDER.index(col) for col in range(7) for row in range(6)]

    def choice(landing, selected):
        unique = [z3.And(*[values[cell] != values[other] for other in landing if other != cell])
                  for cell in landing]
        index = landing.index(selected)
        return z3.And(unique[index], *[z3.Or(z3.UGE(values[cell], values[selected]), z3.Not(unique[j]))
                                     for j, cell in enumerate(landing) if cell != selected])

    for iteration in range(max_iterations):
        result = native.levels(board, levels)
        if result.get('verified'):
            return {'levels': levels, 'verification_nodes': result['nodes'],
                    'iterations': iteration+1, 'synthesis': 'fresh-priority-smt'}
        if result.get('unknown_budget_exceeded'):
            return None
        red, yellow, player = board
        prefix = []
        for move in result['witness']:
            col = int(move)-1
            if player == 1 and (col < 0 or not native.value((*c.place(red, yellow, col, 1), 2))):
                allowed = native.moves((red, yellow, 1))
                if not allowed:
                    raise ValueError('invalid non-winning leaf entry')
                landing = [c.landing(red, yellow, x) for x in c.legal(red, yellow)]
                good = z3.Or(*[choice(landing, c.landing(red, yellow, x)) for x in allowed])
                solver.add(z3.Or(z3.Not(z3.And(*prefix)), good))
                break
            if player == 1 and not c.wins(red, yellow, 1) and not c.wins(red, yellow, 2):
                landing = [c.landing(red, yellow, x) for x in c.legal(red, yellow)]
                prefix.append(choice(landing, c.landing(red, yellow, col)))
            red, yellow = c.place(red, yellow, col, player)
            player = 3-player
        else:
            raise RuntimeError('counterexample has no failing decision')
        if solver.check() != z3.sat:
            return None
        model = solver.model()
        levels = [model.eval(value, model_completion=True).as_long() for value in values]
    return None


def synthesize_response(native, board, max_iterations=256):
    """Fresh per-human-column rank policies; each is exhaustively checked."""
    constraints = [[] for _ in range(8)]
    for iteration in range(max_iterations):
        ranks = [c.rank_constraints(group) for group in constraints]
        if any(row is None for row in ranks):
            return None
        result = native.response(board, ranks)
        if result.get('verified'):
            red, yellow, player = board
            entry = c.ranked(red, yellow, ranks[7])+1 if player == 1 else 0
            return {'responses': ranks[:7], 'entry_move': entry,
                    'verification_nodes': result['nodes'], 'iterations': iteration+1,
                    'synthesis': 'response-cell-orders'}
        if result.get('unknown_budget_exceeded'):
            return None
        red, yellow, player = board
        context = 7
        for move in result['witness']:
            col = int(move)-1
            if player == 1 and not native.value((*c.place(red, yellow, col, 1), 2)):
                allowed = native.moves((red, yellow, 1))
                if not allowed:
                    raise ValueError('non-winning response entry')
                good = {c.landing(red, yellow, x) for x in allowed}
                bad = {c.landing(red, yellow, x) for x in c.legal(red, yellow) if x not in allowed}
                constraints[context].append((good, bad))
                break
            red, yellow = c.place(red, yellow, col, player)
            if player == 2:
                context = col
            player = 3-player
        else:
            raise RuntimeError('response counterexample without a losing decision')
    return None


class Opening:
    def __init__(self, native, output, root, max_iterations=256, synthesis='sat'):
        self.native, self.output, self.max_iterations = native, output, max_iterations
        self.synthesis = synthesis
        if output.exists():
            self.data = json.loads(output.read_text())
            if self.data['root'] != c.state_key(*normalized(*root)[0]):
                raise ValueError('checkpoint root mismatch')
        else:
            self.data = {'format': 'independent-c4-hybrid-v1',
                         'root': c.state_key(*normalized(*root)[0]),
                         'complete': False, 'nodes': {}, 'frontier': [],
                         'source': 'rules only; no imported strategy data'}
        self.last_saved = 0
        self.active = []

    def save(self, force=False):
        now = time.monotonic()
        if force or now-self.last_saved > 10:
            self.data['frontier'] = list(self.active)
            self.data['generator_stats'] = {'oracle_nodes_this_run': self.native.nodes,
                                            'oracle_requests_this_run': self.native.requests,
                                            'seconds_this_run': round(now-self.native.started, 3)}
            temp = self.output.with_suffix('.tmp')
            temp.write_text(json.dumps(self.data, separators=(',', ':'))+'\n')
            temp.replace(self.output)
            self.last_saved = now
            counts = {kind: sum(kind in n for n in self.data['nodes'].values())
                      for kind in ('ranks', 'edges', 'terminal')}
            print(json.dumps({'checkpoint_nodes': len(self.data['nodes']), **counts,
                              'active': self.active[-3:], **self.data['generator_stats']}), flush=True)

    def visit(self, board):
        board, flip = normalized(*board)
        key = c.state_key(*board)
        nodes = self.data['nodes']
        if key in nodes:
            return {'key': key, 'flip': flip}
        self.active.append(key)
        self.save()
        red, yellow, player = board
        if c.four(yellow) or red | yellow == c.FULL:
            raise ValueError('opening search reached a loss/draw')
        if c.four(red):
            node = {'terminal': 'red'}
        elif player == 1:
            immediate = c.wins(red, yellow, 1)
            if immediate:
                col = next(x for x in c.ORDER if x in immediate)
                child = self.visit((*c.place(red, yellow, col, 1), 2))
                node = {'edges': {str(col+1): child}}
            else:
                leaf = None if red | yellow == 0 else (
                    synthesize_response(self.native, board, self.max_iterations) if self.synthesis == 'response'
                    else synthesize_levels(self.native, board, self.max_iterations) if self.synthesis == 'levels'
                    else synthesize_sat(self.native, board, self.max_iterations) if self.synthesis == 'sat'
                    else synthesize(self.native, board, self.max_iterations))
                if leaf:
                    node = leaf
                else:
                    # First prove the chosen move, then cover every Yellow reply.
                    col = next((x for x in c.ORDER if x in c.legal(red, yellow) and
                                self.native.value((*c.place(red, yellow, x, 1), 2))), None)
                    if col is None:
                        raise ValueError(f'no winning move at {key}')
                    child = self.visit((*c.place(red, yellow, col, 1), 2))
                    node = {'edges': {str(col+1): child}}
        else:
            # This board follows a proven winning Red move. All legal replies
            # therefore preserve a Red win; each receives its own certificate.
            edges = {}
            for col in c.ORDER:
                if col in c.legal(red, yellow):
                    edges[str(col+1)] = self.visit((*c.place(red, yellow, col, 2), 1))
            node = {'edges': edges}
        nodes[key] = node
        self.active.pop()
        self.save()
        return {'key': key, 'flip': flip}

    def run(self):
        board = decode(self.data['root'])
        if not self.native.value(board):
            raise ValueError('root is not a strict Red win')
        self.visit(board)
        reachable, pending = set(), [self.data['root']]
        while pending:
            key = pending.pop()
            if key in reachable:
                continue
            reachable.add(key)
            pending.extend(edge['key'] for edge in self.data['nodes'][key].get('edges', {}).values())
        self.data['nodes'] = {key: self.data['nodes'][key] for key in sorted(reachable)}
        self.data['complete'] = True
        self.save(force=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native', type=Path, required=True)
    parser.add_argument('--cache-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--history', default='')
    parser.add_argument('--iterations', type=int, default=256)
    parser.add_argument('--synthesis', choices=('levels', 'sat', 'greedy'), default='greedy')
    parser.add_argument('--budget', type=int, default=500000000)
    args = parser.parse_args()
    with Native(args.native, args.cache_dir, args.budget) as native:
        opening = Opening(native, args.output, c.parse(args.history), args.iterations, args.synthesis)
        try:
            opening.run()
        finally:
            opening.save(force=True)


if __name__ == '__main__':
    main()
