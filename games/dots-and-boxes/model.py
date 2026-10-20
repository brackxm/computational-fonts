# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Complete 2x2-box Dots and Boxes, including scores and extra turns."""
from functools import cache

INITIAL = ((0, (-1,)*4), 0)
TOKENS = tuple(f'{chr(65+x)}{y+1}{direction};' for y in range(3) for x in range(3) for direction in 'HV')
EDGES = {f'{chr(65+x)}{y+1}H;': 2*y+x for y in range(3) for x in range(2)}
EDGES.update({f'{chr(65+x)}{y+1}V;': 6+3*y+x for y in range(2) for x in range(3)})
BOXES = tuple((1 << (2*y+x)) | (1 << (2*(y+1)+x)) | (1 << (6+3*y+x)) | (1 << (6+3*y+x+1))
              for y in range(2) for x in range(2))
FULL = (1 << len(EDGES))-1


def scores(board):
    return board[1].count(0), board[1].count(1)


@cache
def moves(node):
    (edges, owners), side = node
    result = {}
    for token, index in EDGES.items():
        bit = 1 << index
        if edges & bit:
            continue
        changed = edges | bit
        claimed = tuple(side if owner == -1 and changed & mask == mask else owner
                        for owner, mask in zip(owners, BOXES))
        result[token] = (changed, claimed), side if claimed != owners else 1-side
    return result


def winner(node):
    if node[0][0] != FULL:
        return None
    a, b = scores(node[0])
    return 2 if a == b else 0 if a > b else 1


@cache
def margin(node):
    """Optimal final first-player score minus second-player score."""
    if winner(node) is not None:
        a, b = scores(node[0])
        return a-b
    outcomes = [margin(child) for child in moves(node).values()]
    return max(outcomes) if node[1] == 0 else min(outcomes)


def choose(node):
    return min(token for token, child in moves(node).items() if margin(child) == margin(node))
