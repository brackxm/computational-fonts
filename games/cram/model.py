# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Normal-play 6x5 Cram, with the exact central-domino/half-turn strategy."""
COLS, ROWS = 6,5
SIZE = COLS*ROWS
START, END = '\ue000','\ue001'
OPENING = 'C3H'
SIDES = {'H':('L','R'),'V':('T','B')}
MOVES = {}
for row in range(ROWS):
    for col in range(COLS):
        for orientation,(dx,dy) in (('H',(1,0)),('V',(0,1))):
            if col+dx<COLS and row+dy<ROWS:
                MOVES[f'{chr(65+col)}{row+1}{orientation}']=(row*COLS+col,(row+dy)*COLS+col+dx)
BY_CELLS = {cells:key for key,cells in MOVES.items()}
MIRROR = {key:BY_CELLS[tuple(sorted(SIZE-1-c for c in cells))] for key,cells in MOVES.items()}


def legal(cells,key):
    return key in MOVES and all(cells[c]=='.' for c in MOVES[key])


def place(cells,key,owner):
    if not legal(cells,key):raise ValueError('Illegal domino')
    cells=list(cells)
    for cell,side in zip(MOVES[key],SIDES[key[-1]]):cells[cell]=owner+side
    return tuple(cells)


def available(cells):
    return [key for key in MOVES if legal(cells,key)]


def replay(source):
    text=''.join(c for c in source if c not in ' \t\r\n')
    cells=tuple('.' for _ in range(SIZE));last=None
    if not text.startswith('b'):return cells,last,'malformed'
    cells=place(cells,OPENING,'a');last=OPENING
    text=text[1:]
    while text:
        if len(text)<3 or text[0] not in 'ABCDEF' or text[1] not in '12345' or text[2] not in 'HV':
            return cells,last,'malformed'
        key=text[:3]
        if not legal(cells,key):return cells,last,'invalid'
        cells=place(cells,key,'h')
        response=MIRROR[key]
        if not legal(cells,response):return cells,last,'internal'
        cells=place(cells,response,'a');last=response
        if not available(cells):return cells,last,'computer_won'
        text=text[3:]
    return cells,last,'ready'
