"""Independent normal-order reference, imported only by tests/benchmarks."""
from dataclasses import dataclass
from .syntax import App,Leaf,parse,prefix,height

@dataclass(frozen=True)
class ReferenceResult:
    status:str
    expression:str
    steps:int

def step(t):
    head=t;args=[]
    while isinstance(head,App):
        args.append(head.right);head=head.left
    args.reverse()
    arity={'I':1,'K':2,'S':3}.get(head.value)
    if arity and len(args)>=arity:
        x=args[0]
        if head.value in ('I','K'):out=x
        else:
            y,z=args[1:3];out=App(App(x,z),App(y,z))
        for extra in args[arity:]:out=App(out,extra)
        return out
    if isinstance(t,App):
        left=step(t.left)
        if left is not None:return App(left,t.right)
        right=step(t.right)
        if right is not None:return App(t.left,right)
    return None

def evaluate(source,depth=5,fuel=32):
    t=parse(source)
    if height(t)>depth:return ReferenceResult('input_overflow',prefix(t),0)
    for i in range(fuel+1):
        nxt=step(t)
        if nxt is None:return ReferenceResult('normal',prefix(t),i)
        if i==fuel:return ReferenceResult('budget',prefix(t),i)
        if height(nxt)>depth:return ReferenceResult('overflow',prefix(t),i)
        t=nxt
    raise AssertionError('unreachable')
