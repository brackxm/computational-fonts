# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Complete 4x4 Domineering. First player is Vertical, second Horizontal."""
from functools import cache

INITIAL = ((0, 0), 0)
TOKENS = tuple(f'{chr(65+x)}{y+1}{direction};' for y in range(4) for x in range(4) for direction in 'VH')


@cache
def moves(node):
    (vertical, horizontal), side = node
    occupied = vertical | horizontal
    result = {}
    for i in range(16):
        if (side == 0 and i//4 == 3) or (side == 1 and i%4 == 3):
            continue
        mask = (1 << i) | (1 << (i+(4 if side == 0 else 1)))
        if occupied & mask:
            continue
        board = (vertical | mask, horizontal) if side == 0 else (vertical, horizontal | mask)
        result[f'{chr(65+i%4)}{i//4+1}{"V" if side == 0 else "H"};'] = board, 1-side
    return result


def winner(node):
    return 1-node[1] if not moves(node) else None
