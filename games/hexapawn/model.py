# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Complete 3x3 Hexapawn rules and exact acyclic minimax solution."""
from functools import lru_cache

INITIAL='www...bbb'  # A1 B1 C1, A2 B2 C2, A3 B3 C3.
START,END='\ue000','\ue001'


def opponent(side):return 'b' if side=='w' else 'w'


def square(index):return chr(65+index%3)+str(index//3+1)


@lru_cache(None)
def moves(board,side):
    result={};step=1 if side=='w' else -1
    for origin,piece in enumerate(board):
        if piece!=side:continue
        rank,file=divmod(origin,3)
        next_rank=rank+step
        if not 0<=next_rank<3:continue
        for next_file in range(max(0,file-1),min(3,file+2)):
            target=next_rank*3+next_file
            allowed=board[target]=='.' if next_file==file else board[target]==opponent(side)
            if allowed:
                cells=list(board);cells[origin]='.';cells[target]=side
                result[square(origin)+square(target)]=''.join(cells)
    return result


def winner(board,to_move):
    if 'w' in board[6:]:return 'w'
    if 'b' in board[:3]:return 'b'
    if 'w' not in board:return 'b'
    if 'b' not in board:return 'w'
    if not moves(board,to_move):return opponent(to_move)
    return None


def remaining_distance(board):
    return sum(2-i//3 if piece=='w' else i//3 if piece=='b' else 0 for i,piece in enumerate(board))


@lru_cache(None)
def solve(board,side):
    end=winner(board,side)
    if end is not None:return (1 if end==side else -1),0
    outcomes=[]
    for child in moves(board,side).values():
        value,distance=solve(child,opponent(side))
        outcomes.append((-value,distance+1))
    value=max(v for v,d in outcomes)
    ranks=[d for v,d in outcomes if v==value]
    return value,min(ranks) if value==1 else max(ranks)


def choose(board,side):
    if winner(board,side) is not None:return None
    value,distance=solve(board,side)
    return min(key for key,child in moves(board,side).items()
               if solve(child,opponent(side))==(-value,distance-1))


@lru_cache(None)
def graph():
    pending=[(INITIAL,'w')];seen=set(pending)
    while pending:
        board,side=pending.pop()
        if winner(board,side) is not None:continue
        for child in moves(board,side).values():
            node=child,opponent(side)
            if node not in seen:seen.add(node);pending.append(node)
    return tuple(sorted(seen))


def reply(board,human):
    ai=opponent(human)
    if winner(board,ai) is not None:return board,None,'human_won'
    key=choose(board,ai);child=moves(board,ai)[key]
    return child,key,'computer_won' if winner(child,human) is not None else 'ready'


def replay(source):
    text=''.join(c for c in source if c not in ' \t\r\n')
    board,last=INITIAL,None
    if not text or text[0] not in 'hb':return board,last,'malformed'
    human='w' if text[0]=='h' else 'b'
    if text[0]=='b':board,last,status=reply(board,human)
    else:status='ready'
    text=text[1:]
    while text and status=='ready':
        if len(text)<4 or any(text[i] not in 'ABC' for i in (0,2)) or any(text[i] not in '123' for i in (1,3)):
            return board,last,'malformed'
        key=text[:4];options=moves(board,human)
        if key not in options:return board,last,'invalid'
        board=options[key]
        child,move,status=reply(board,human);board=child
        if move is not None:last=move
        text=text[4:]
    return board,last,status
