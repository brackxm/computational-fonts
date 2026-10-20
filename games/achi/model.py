# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Berkeley's three-counter Achi variant, with standard board diagonals."""
from functools import cache

INITIAL = ('.'*9, 0)
DRAW_OFFER = HINTS = True
LINES = ((0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6))


def square(i):
    return chr(65+i%3)+str(i//3+1)


TOKENS = tuple([square(i)+';' for i in range(9)]
               + [square(i)+square(j)+';' for i in range(9) for j in range(9)])
EDGES = {tuple(sorted((a, b))) for line in LINES for a, b in zip(line, line[1:])}
NEIGHBORS = {i: tuple(j for j in range(9) if tuple(sorted((i, j))) in EDGES) for i in range(9)}


@cache
def moves(node):
    board, side = node
    result = {}
    if board.count('.') > 3:
        return {square(i)+';': (board[:i]+str(side)+board[i+1:], 1-side)
                for i in range(9) if board[i] == '.'}
    for origin, piece in enumerate(board):
        if piece != str(side):
            continue
        for target in NEIGHBORS[origin]:
            if board[target] != '.':
                continue
            cells = list(board)
            cells[origin], cells[target] = '.', piece
            result[square(origin)+square(target)+';'] = ''.join(cells), 1-side
    return result


def winner(node):
    board, side = node
    for a, b, c in LINES:
        if board[a] == board[b] == board[c] != '.':
            return int(board[a])
    return 1-side if not moves(node) else None
