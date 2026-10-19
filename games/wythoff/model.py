# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Wythoff's Nim on two configurable heaps, each initially at most 63."""
from math import isqrt
from functools import lru_cache

MAX_HEAP = 63
DEFAULT = 'b31,47;'
START, END = '\ue000','\ue001'


def cold(a,b):
    a,b=sorted((a,b))
    n=b-a
    return a == (n+isqrt(5*n*n))//2


def moves(a,b):
    for kind,limit in (('A',a),('B',b),('D',min(a,b))):
        for amount in range(1,limit+1):
            yield kind,amount


def apply(heaps,move):
    kind,n=move
    a,b=heaps
    if kind not in ('A','B','D') or not isinstance(n,int) or not 1 <= n <= MAX_HEAP:
        raise ValueError('Invalid move')
    if kind in 'AD':a-=n
    if kind in 'BD':b-=n
    if min(a,b)<0:raise ValueError('Not enough tokens')
    return a,b


@lru_cache(maxsize=(MAX_HEAP+1)**2)
def choose(heaps):
    fallback=None
    for move in moves(*heaps):
        if fallback is None:fallback=move
        if cold(*apply(heaps,move)):return move
    return fallback


def describe(heaps,move,after):
    """Compact font annotation: target heap size, or a losing-state fallback."""
    if cold(*heaps):return ('take_A',1)
    kind,_=move
    if kind=='D':return (kind,*after)
    return kind,after[0 if kind=='A' else 1]


def replay(source):
    text=''.join(c for c in source if c not in ' \t\r\n')
    a,b,last=0,0,None
    if not text or text[0] not in 'bh':return (a,b),last,'malformed'
    first=text[0]; text=text[1:]
    def number(s):
        return len(s)>=2 and all(c in '0123456789' for c in s[:2]) and int(s[:2])<=MAX_HEAP
    if not number(text):return (a,b),last,'malformed'
    a=int(text[:2]);text=text[2:]
    if not text.startswith(','):return (a,b),last,'malformed'
    text=text[1:]
    if not number(text):return (a,b),last,'malformed'
    b=int(text[:2]);text=text[2:]
    if not text.startswith(';'):return (a,b),last,'malformed'
    text=text[1:]
    heaps=(a,b)
    if heaps==(0,0):return heaps,last,'invalid'
    if first=='b':
        move=choose(heaps);after=apply(heaps,move)
        last=describe(heaps,move,after);heaps=after
        if heaps==(0,0):return heaps,last,'computer_won'
    while text:
        if len(text)<4 or text[0] not in 'ABD' or not number(text[1:]) or text[3]!=';' or text[1:3]=='00':
            return heaps,last,'malformed'
        move=(text[0],int(text[1:3]))
        try:heaps=apply(heaps,move)
        except ValueError:return heaps,last,'invalid'
        if heaps==(0,0):return heaps,last,'human_won'
        move=choose(heaps);after=apply(heaps,move)
        last=describe(heaps,move,after);heaps=after
        if heaps==(0,0):return heaps,last,'computer_won'
        text=text[4:]
    return heaps,last,'ready'
