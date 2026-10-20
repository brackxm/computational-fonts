# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Standard 3x3 Dodgem; blue (0) exits east, red (1) exits north."""
from functools import cache

INITIAL = ('.110..0..', 0)
DIRECTIONS = (((1, 0), (0, 1), (0, -1)), ((0, 1), (1, 0), (-1, 0)))


def square(i):
    return chr(65+i%3)+str(i//3+1)


TOKENS = tuple(sorted({square(i)+square(j)+';' for i in range(9) for j in range(9)}
                      | {square(i)+'X;' for i in range(9)}))


@cache
def moves(node):
    board, side = node
    result = {}
    for origin, piece in enumerate(board):
        if piece != str(side):
            continue
        x, y = origin%3, origin//3
        for dx, dy in DIRECTIONS[side]:
            nx, ny = x+dx, y+dy
            cells = list(board)
            cells[origin] = '.'
            if 0 <= nx < 3 and 0 <= ny < 3:
                target = ny*3+nx
                if board[target] != '.':
                    continue
                cells[target] = piece
                token = square(origin)+square(target)+';'
            elif (side == 0 and nx == 3) or (side == 1 and ny == 3):
                token = square(origin)+'X;'
            else:
                continue
            result[token] = (''.join(cells), 1-side)
    return result


def winner(node):
    board, side = node
    for player in (0, 1):
        if str(player) not in board:
            return player
    return 1-side if not moves(node) else None
