# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Exact loopy-game solution for Mū tōrere with the usual centre-entry rule."""
from collections import defaultdict,deque
from functools import lru_cache
from itertools import combinations

INITIAL='hhhhaaaa.'
START,END='\ue000','\ue001'
POSITIONS=[]
for empty in range(9):
    for human in combinations([i for i in range(9) if i!=empty],4):
        POSITIONS.append(''.join('.' if i==empty else 'h' if i in human else 'a' for i in range(9)))
POSITIONS=tuple(sorted(POSITIONS))
IDS={position:i for i,position in enumerate(POSITIONS)}


def opponent(player):return 'a' if player=='h' else 'h'


@lru_cache(None)
def moves(position,player):
    target=position.index('.')
    result={}
    for source,piece in enumerate(position):
        if piece!=player:continue
        if source==8:
            allowed=True
        elif target==8:
            allowed=any(position[i]==opponent(player) for i in ((source-1)%8,(source+1)%8))
        else:allowed=target in ((source-1)%8,(source+1)%8)
        if allowed:
            cells=list(position);cells[source],cells[target]='.',player
            result[source]=''.join(cells)
    return result


@lru_cache(None)
def solve():
    graph={(position,player):tuple((child,opponent(player)) for child in moves(position,player).values())
           for position in POSITIONS for player in 'ha'}
    parents=defaultdict(list)
    remaining={node:len(children) for node,children in graph.items()}
    for node,children in graph.items():
        for child in children:parents[child].append(node)
    value={node:-1 for node,children in graph.items() if not children}
    distance={node:0 for node in value}
    longest=defaultdict(int)
    pending=deque(value)
    while pending:
        child=pending.popleft()
        for parent in parents[child]:
            if parent in value:continue
            if value[child]==-1:
                value[parent]=1;distance[parent]=distance[child]+1;pending.append(parent)
            else:
                remaining[parent]-=1
                longest[parent]=max(longest[parent],distance[child])
                if remaining[parent]==0:
                    value[parent]=-1;distance[parent]=longest[parent]+1;pending.append(parent)
    for node in graph:
        if node not in value:value[node]=0;distance[node]=None
    return value,distance


def choose(position,player='a'):
    value,distance=solve()
    options=moves(position,player)
    if not options:return None
    outcome=value[position,player]
    candidates=[source for source,child in options.items() if value[child,opponent(player)]==-outcome]
    if outcome==1:
        return min(candidates,key=lambda source:(distance[options[source],opponent(player)],source))
    if outcome==-1:
        return min(candidates,key=lambda source:(-distance[options[source],opponent(player)],source))
    return min(candidates)


def reply(position):
    """Complete AI turn, including terminal positions; last is source,target."""
    source=choose(position)
    if source is None:return position,None,'human_won'
    target=position.index('.')
    child=moves(position,'a')[source]
    return child,(source,target),'ready' if moves(child,'h') else 'computer_won'


@lru_cache(None)
def starts():
    values,distance=solve()
    return {'h':INITIAL,'b':INITIAL,
            'w':next(p for p in POSITIONS if values[p,'h']==1 and distance[p,'h']==5),
            'l':next(p for p in POSITIONS if values[p,'h']==-1 and distance[p,'h']==4)}


def replay(source):
    text=''.join(c for c in source if c not in ' \t\r\n')
    position,last=INITIAL,None
    if not text or text[0] not in starts():return position,last,'malformed'
    position=starts()[text[0]]
    if text[0]=='b':position,last,status=reply(position)
    else:status='ready'
    text=text[1:]
    for token in text:
        if status!='ready':break
        if token=='=':
            # Draws by agreement do not manufacture a draw from a forced AI win.
            if solve()[0][position,'h']>=0:status='draw'
            else:status='invalid'
            break
        if token not in '123456789':status='malformed';break
        origin=int(token)-1
        options=moves(position,'h')
        if origin not in options:status='invalid';break
        position=options[origin]
        child,move,status=reply(position)
        position=child
        if move is not None:last=move
    return position,last,status
