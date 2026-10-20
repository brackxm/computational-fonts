# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Normal-play Kayles with twelve numbered pins and fixed adjacency."""
from functools import cache

PINS = 12
INITIAL = ((1 << PINS)-1, 0)
TOKENS = tuple(f'{i+1:02}{kind};' for i in range(PINS) for kind in 'SD')
REMOVALS = {f'{i+1:02}{kind};': ((1 << count)-1) << i
            for i in range(PINS) for kind, count in (('S', 1), ('D', 2)) if i+count <= PINS}


@cache
def moves(node):
    board, side = node
    return {token: (board ^ mask, 1-side) for token, mask in REMOVALS.items() if board & mask == mask}


def winner(node):
    return 1-node[1] if not node[0] else None
