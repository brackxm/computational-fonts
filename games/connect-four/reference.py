# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: GPL-3.0-only
"""Independent row-major game model. Uses the pinned WeakC4 policy data.

This model is test tooling only; the playground never imports it.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent / 'upstream/solution'
BRANCHES = json.loads((ROOT / 'branches.json').read_text())
DIAGRAMS = json.loads((ROOT / 'steady_states.json').read_text())
OPENINGS = [p for p, v in BRANCHES.items() if isinstance(v, str)]


def empty():
    return [[0] * 7 for _ in range(6)]


def drop(board, col, player):
    for row in range(6):
        if not board[row][col]:
            board[row][col] = player
            return row
    return None


def board_of(sequence):
    board = empty()
    for ply, col in enumerate(sequence):
        if drop(board, int(col)-1, 1+ply%2) is None:
            raise ValueError(f'Full column in position {sequence!r}')
    return board


def key(board):
    return tuple(tuple(row) for row in board)


def mirror(board):
    return [row[::-1] for row in board]


def won(board, player):
    for y in range(6):
        for x in range(7):
            for dx, dy in ((1, 0), (0, 1), (1, 1), (1, -1)):
                if all(0 <= x+i*dx < 7 and 0 <= y+i*dy < 6 and
                       board[y+i*dy][x+i*dx] == player for i in range(4)):
                    return True
    return False


def wins(board, player):
    result = []
    for col in range(7):
        test = [row[:] for row in board]
        if drop(test, col, player) is not None and won(test, player):
            result.append(col+1)
    return result


TARGETS = {}
for sequence, instruction in BRANCHES.items():
    mode = ('branch', OPENINGS.index(sequence), 0) if isinstance(instruction, str) else ('leaf', instruction, 0)
    board = board_of(sequence)
    TARGETS[key(board)] = mode
    TARGETS.setdefault(key(mirror(board)), (mode[0], mode[1], 1))


def transition(mode, yellow):
    kind, index, flip = mode
    if kind != 'branch':
        return mode
    seq = OPENINGS[index] + BRANCHES[OPENINGS[index]]
    if flip:
        seq = ''.join(str(8-int(c)) for c in seq)
    board = board_of(seq)
    if drop(board, yellow-1, 2) is None:
        return ('invalid', 0, 0)
    return TARGETS.get(key(board), ('urgent', 0, 0))


def choose(board, mode):
    for player in (1, 2):
        columns = wins(board, player)
        if columns:
            return columns[0]
    kind, index, flip = mode
    if kind == 'branch':
        col = int(BRANCHES[OPENINGS[index]])
        return 8-col if flip else col
    if kind != 'leaf':
        return None
    available = [[] for _ in range(10)]
    for col in range(7):
        row = next((y for y in range(6) if not board[y][col]), 6)
        if row < 6:
            level = int(DIAGRAMS[index][5-row][6-col if flip else col])
            available[level].append(col+1)
    return next((cols[0] for cols in available if len(cols) == 1), None)


def replay(source):
    board, mode, last = board_of('4'), ('branch', OPENINGS.index(''), 0), 4
    if not source.startswith('b'):
        return board, 'malformed', last, mode, []
    status, replies = 'ready', []
    for char in source[1:]:
        if status == 'win':
            status = 'trailing'
            break
        if char not in '1234567':
            status = 'malformed'
            break
        col = int(char)
        if drop(board, col-1, 2) is None:
            status = 'full'
            break
        if won(board, 2):
            status = 'yellow'
            break
        if all(board[5]):
            status = 'draw'
            break
        mode = transition(mode, col)
        reply = choose(board, mode)
        if reply is None or drop(board, reply-1, 1) is None:
            status = 'internal'
            break
        last = reply
        replies.append(reply)
        if won(board, 1):
            status = 'win'
    return board, status, last, mode, replies
