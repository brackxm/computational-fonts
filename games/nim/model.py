# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Exact normal/misère Nim for three configurable heaps of at most 31."""
from functools import lru_cache

MAX_HEAP=31
DEFAULT='bN03,05,07;'
START,END='\ue000','\ue001'


def winning(heaps,mode='N'):
    if mode=='M' and all(n<=1 for n in heaps):return sum(heaps)%2==0
    return heaps[0]^heaps[1]^heaps[2]!=0


def moves(heaps):
    for heap,size in enumerate(heaps):
        for amount in range(1,size+1):yield heap,amount


def apply(heaps,move):
    heap,amount=move
    if heap not in (0,1,2) or not isinstance(amount,int) or not 1<=amount<=heaps[heap]:
        raise ValueError('Illegal take')
    result=list(heaps);result[heap]-=amount
    return tuple(result)


@lru_cache(maxsize=65536)
def choose(heaps,mode='N'):
    fallback=None
    for move in moves(heaps):
        if fallback is None:fallback=move
        if not winning(apply(heaps,move),mode):return move
    return fallback


def describe(heaps,mode,move,after):
    heap,amount=move
    # The font uses fixed target actions for the small misère endgame, and
    # one-token fallback actions for other losing positions.
    special=mode=='M' and sum(n>1 for n in heaps)<=1
    if not special and heaps[0]^heaps[1]^heaps[2]==0:return 'take',heap,1
    return 'target',heap,after[heap]


def replay(source):
    text=''.join(c for c in source if c not in ' \t\r\n')
    heaps=[0,0,0];last=None;mode='N'
    if not text or text[0] not in 'bh':return tuple(heaps),mode,last,'malformed'
    first=text[0];text=text[1:]
    if not text or text[0] not in 'NM':return tuple(heaps),mode,last,'malformed'
    mode=text[0];text=text[1:]
    def number(s):return len(s)>=2 and all(c in '0123456789' for c in s[:2]) and int(s[:2])<=MAX_HEAP
    for heap in range(3):
        if not number(text):return tuple(heaps),mode,last,'malformed'
        heaps[heap]=int(text[:2]);text=text[2:]
        delimiter=',' if heap<2 else ';'
        if not text.startswith(delimiter):return tuple(heaps),mode,last,'malformed'
        text=text[1:]
    heaps=tuple(heaps)
    if not any(heaps):return heaps,mode,last,'invalid'
    def computer(heaps):
        move=choose(heaps,mode);child=apply(heaps,move)
        annotation=describe(heaps,mode,move,child)
        return child,annotation,('computer_won' if mode=='N' else 'human_won') if not any(child) else 'ready'
    if first=='b':
        heaps,last,status=computer(heaps)
        if status!='ready':return heaps,mode,last,status
    while text:
        if len(text)<4 or text[0] not in 'ABC' or not number(text[1:]) or text[1:3]=='00' or text[3]!=';':
            return heaps,mode,last,'malformed'
        move=ord(text[0])-65,int(text[1:3])
        try:heaps=apply(heaps,move)
        except ValueError:return heaps,mode,last,'invalid'
        if not any(heaps):return heaps,mode,last,'human_won' if mode=='N' else 'computer_won'
        heaps,last,status=computer(heaps)
        if status!='ready':return heaps,mode,last,status
        text=text[4:]
    return heaps,mode,last,'ready'
