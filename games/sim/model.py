# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Standard six-vertex Sim. A monochromatic triangle loses immediately."""
from itertools import combinations

EDGES = tuple(combinations(range(6), 2))
TOKENS = tuple(chr(65+a)+chr(65+b)+';' for a, b in EDGES)
POWERS = tuple(3**i for i in range(15))
TRIANGLES = tuple(sum(1 << EDGES.index(e) for e in combinations(v, 2))
                  for v in combinations(range(6), 3))
INITIAL = (0, 0)


def masks(code):
    first = second = 0
    for i in range(15):
        code, digit = divmod(code, 3)
        if digit == 1:
            first |= 1 << i
        elif digit == 2:
            second |= 1 << i
    return first, second


def winner(node):
    for side, mask in enumerate(masks(node[0])):
        if any(mask & triangle == triangle for triangle in TRIANGLES):
            return 1-side
    return None


def moves(node):
    code, side = node
    return {token: (code+(side+1)*power, 1-side)
            for token, power in zip(TOKENS, POWERS) if code//power % 3 == 0}
