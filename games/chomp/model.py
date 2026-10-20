# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Exact 6-column, 5-row Chomp. Rows grow upwards from poisoned A1."""
from functools import cache

WIDTH, HEIGHT = 6, 5
INITIAL = ((WIDTH,) * HEIGHT, 0)
TOKENS = tuple(f'{chr(65+x)}{y+1};' for y in range(HEIGHT) for x in range(WIDTH))


@cache
def moves(node):
    rows, side = node
    return {f'{chr(65+x)}{y+1};': (rows[:y]+tuple(min(n, x) for n in rows[y:]), 1-side)
            for y, length in enumerate(rows) for x in range(length) if (x, y) != (0, 0)}


def winner(node):
    return 1-node[1] if node[0] == (1, 0, 0, 0, 0) else None
