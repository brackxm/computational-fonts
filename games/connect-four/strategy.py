# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: GPL-3.0-only
"""Strategy compiler inputs. Column-major graph construction from the probe.

The separate row-major reference.py supplies the differential test oracle.
"""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent / 'upstream'
BRANCHES = json.loads((ROOT/'solution/branches.json').read_text())
DIAGRAMS = json.loads((ROOT/'solution/steady_states.json').read_text())
OPENINGS = [p for p,v in BRANCHES.items() if isinstance(v,str)]
def board_of(sequence):
    columns = [[] for _ in range(7)]
    for i, c in enumerate(sequence):
        x = int(c)-1
        assert len(columns[x]) < 6
        columns[x].append(1 + i % 2)
    return tuple(tuple(c+[0]*(6-len(c))) for c in columns)


def mirrored(board):
    return board[::-1]


LINES = []
for x in range(7):
    for y in range(6):
        for dx, dy in ((1,0), (0,1), (1,1), (1,-1)):
            cells = [(x+i*dx, y+i*dy) for i in range(4)]
            if all(0 <= a < 7 and 0 <= b < 6 for a,b in cells):
                LINES.append(cells)
assert len(LINES) == 69


def winning_columns(board, who):
    result = []
    for x in range(7):
        y = next((i for i,v in enumerate(board[x]) if not v), 6)
        if y == 6:
            continue
        if any((x,y) in line and all((a,b)==(x,y) or board[a][b]==who
                                    for a,b in line) for line in LINES):
            result.append(x+1)
    return result


TARGETS = {}
for sequence, instruction in BRANCHES.items():
    mode = ('branch', OPENINGS.index(sequence)) if isinstance(instruction,str) else ('leaf', instruction)
    board = board_of(sequence)
    TARGETS[board] = (*mode,0)
    TARGETS.setdefault(mirrored(board), (*mode,1))


def transition(mode, yellow):
    _, index, flip = mode
    sequence = OPENINGS[index] + BRANCHES[OPENINGS[index]]
    if flip:
        sequence = ''.join(str(8-int(c)) for c in sequence)
    if board_of(sequence)[yellow-1][-1]:
        return ('invalid', 0, 0)
    after = board_of(sequence + str(yellow))
    if after in TARGETS:
        return TARGETS[after]
    assert winning_columns(after, 1), (index, flip, yellow)
    return ('urgent', 0, 0)
