# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Exact standard 3x3 tic-tac-toe; deterministic perfect play on either side."""
from functools import lru_cache

INITIAL='.'*9
START,END='\ue000','\ue001'
LINES=((0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6))
PREFERENCE=(4,0,2,6,8,1,3,5,7)


def opponent(side):return 'o' if side=='x' else 'x'


def winner(board):
    for line in LINES:
        side=board[line[0]]
        if side!='.' and all(board[i]==side for i in line):return side
    return '=' if '.' not in board else None


def moves(board,side):
    if winner(board) is not None:return {}
    return {str(i+1):board[:i]+side+board[i+1:] for i in range(9) if board[i]=='.'}


@lru_cache(None)
def solve(board,side):
    end=winner(board)
    if end is not None:return (0 if end=='=' else 1 if end==side else -1),0
    outcomes=[(-v,d+1) for child in moves(board,side).values() for v,d in [solve(child,opponent(side))]]
    value=max(v for v,d in outcomes)
    distances=[d for v,d in outcomes if v==value]
    return value,min(distances) if value==1 else max(distances)


def choose(board,side):
    if winner(board) is not None:return None
    value,distance=solve(board,side);options=moves(board,side)
    for i in PREFERENCE:
        key=str(i+1)
        child=options.get(key)
        if child is not None and solve(child,opponent(side))==(-value,distance-1):return key
    raise AssertionError('A solved nonterminal position needs an optimal move')


@lru_cache(None)
def graph():
    pending=[(INITIAL,'x')];seen=set(pending)
    while pending:
        board,side=pending.pop()
        for child in moves(board,side).values():
            node=child,opponent(side)
            if node not in seen:seen.add(node);pending.append(node)
    return tuple(sorted(seen))


def outcome(board,human):
    end=winner(board)
    if end is None:return 'ready'
    return 'draw' if end=='=' else 'human_won' if end==human else 'computer_won'


def reply(board,human):
    status=outcome(board,human)
    if status!='ready':return board,None,status
    ai=opponent(human);key=choose(board,ai);child=moves(board,ai)[key]
    return child,key,outcome(child,human)


@lru_cache(None)
def policy_graph():
    """All human-turn positions reachable from either start against this policy."""
    initial=[(INITIAL,'x'),(reply(INITIAL,'o')[0],'o')]
    seen=set(initial);pending=list(initial)
    while pending:
        board,human=pending.pop()
        for child in moves(board,human).values():
            after,last,status=reply(child,human)
            node=after,human
            if status=='ready' and node not in seen:seen.add(node);pending.append(node)
    return tuple(sorted(seen))


def replay(source):
    text=''.join(c for c in source if c not in ' \t\r\n')
    board,last=INITIAL,None
    if not text or text[0] not in 'hb':return board,last,'malformed'
    human='x' if text[0]=='h' else 'o'
    if human=='o':board,last,status=reply(board,human)
    else:status='ready'
    for key in text[1:]:
        if status!='ready':break
        if key not in '123456789':return board,last,'malformed'
        options=moves(board,human)
        if key not in options:return board,last,'invalid'
        board,move,status=reply(options[key],human)
        if move is not None:last=move
    return board,last,status
