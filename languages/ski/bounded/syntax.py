"""SKI syntax and tree serialization only; no reductions."""
from dataclasses import dataclass

ALPHABET='SKIabcdefghijklmnopqrstuvwxyz'
@dataclass(frozen=True)
class Leaf:
    value: str
@dataclass(frozen=True)
class App:
    left: object
    right: object

def prefix(t):
    out=[];todo=[t]
    while todo:
        node=todo.pop()
        if isinstance(node,Leaf):out.append(node.value)
        else:
            out.append('@');todo.extend((node.right,node.left))
    return ''.join(out)

def pretty(t):
    if isinstance(t,Leaf):return t.value
    return pretty(t.left)+' '+('('+pretty(t.right)+')' if isinstance(t.right,App) else pretty(t.right))

def parse(source):
    if not isinstance(source,str):raise TypeError('source must be a string')
    if len(source)>16384:raise ValueError('source exceeds 16384-character input limit')
    s=''.join(source.split())
    if not s:raise ValueError('empty expression')
    i=0
    def one(depth=0):
        nonlocal i
        if depth>128:raise ValueError('prefix nesting exceeds parser limit')
        if i>=len(s):raise ValueError('incomplete application')
        c=s[i];i+=1
        if c in ALPHABET:return Leaf(c)
        if c=='@':return App(one(depth+1),one(depth+1))
        raise ValueError(f'invalid prefix token {c!r}')
    def group(depth=0):
        nonlocal i
        if depth>128:raise ValueError('parenthesis nesting exceeds parser limit')
        ts=[]
        while i<len(s) and s[i]!=')':
            c=s[i];i+=1
            if c=='(':
                t=group(depth+1)
                if i>=len(s) or s[i]!=')':raise ValueError('unclosed parenthesis')
                i+=1
            elif c in ALPHABET:t=Leaf(c)
            else:raise ValueError(f'invalid token {c!r}')
            ts.append(t)
        if not ts:raise ValueError('empty parenthesis')
        t=ts[0]
        for x in ts[1:]:t=App(t,x)
        return t
    t=one() if '@' in s else group()
    if i!=len(s):raise ValueError('trailing expression or unmatched parenthesis')
    return t

def height(t):
    maximum=0;todo=[(t,0)]
    while todo:
        node,depth=todo.pop();maximum=max(maximum,depth)
        if isinstance(node,App):todo.extend(((node.left,depth+1),(node.right,depth+1)))
    return maximum

def count(t):
    return len(prefix(t))
