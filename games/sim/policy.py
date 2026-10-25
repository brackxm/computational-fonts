# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Build-time exact table and the two policy closures needed by the font."""
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'shared'))
from exactgame import Policy
import model


def solve_table():
    with tempfile.TemporaryDirectory() as directory:
        executable, output = Path(directory)/'solve', Path(directory)/'values'
        subprocess.run(['c++', '-std=c++17', '-O3', str(Path(__file__).with_name('solver.cpp')),
                        '-o', str(executable)], check=True)
        subprocess.run([str(executable), str(output)], check=True)
        return memoryview(output.read_bytes()).cast('b')


class Graph:
    def __getitem__(self, node):
        return {} if model.winner(node) is not None else model.moves(node)


class SimPolicy(Policy):
    def __init__(self, table=None):
        self.rules = model
        self.table = solve_table() if table is None else table
        self.graph = Graph()
        nodes = {model.INITIAL}
        self.active_counts = []
        for human in (0, 1):
            pending, seen = [model.INITIAL], set()
            while pending:
                node = pending.pop()
                if node in seen:
                    continue
                seen.add(node)
                nodes.add(node)
                if model.winner(node) is not None:
                    continue
                options = self.graph[node]
                pending.extend(options.values() if node[1] == human else [options[self.choose(node)]])
            self.active_counts.append(sum(n[1] == human and model.winner(n) is None for n in seen))
        self.nodes = tuple(sorted(nodes))
        self.outcomes = {node: self.solve(node)[0] for node in self.nodes}

    def solve(self, node):
        value = self.table[node[0]]
        if not value:
            raise ValueError('Position is outside the solved legal game')
        return (node[1] if value > 0 else 1-node[1], abs(value)-1)

    def choose(self, node):
        winner, _ = self.solve(node)
        return min(token for token, child in self.graph[node].items()
                   if self.solve(child)[0] == winner)
