"""V44: depth-six 16-round HarfBuzz differential regression."""
import argparse
import random
from collections import Counter
from .runtime import Machine, InputOverflow
from .reference import evaluate
from .syntax import App, Leaf, prefix

def run(font='build/v44-depth6-r16.ttf', samples=1000):
    rng=random.Random(43044)
    def tree(depth):
        if not depth or rng.random()<.46:
            return Leaf(rng.choice('SKIabcdef'))
        return App(tree(depth-1),tree(depth-1))
    fixed=['@Ia','@@Kab','@@@SKKa','@@@Sab@@Kcd','@@@S@Iabc','@@Ka@@@SIIb']
    counts=Counter()
    with Machine(font) as machine:
        assert machine.depth==6 and machine.rounds==16
        for k in range(samples+len(fixed)):
            expression=prefix(tree(6)) if k>=len(fixed) else fixed[k]
            fuel=rng.randrange(17)
            expected=evaluate(expression,6,fuel)
            try:
                result=machine.run(expression,fuel)
                actual=(result.status,result.expression,result.steps)
            except InputOverflow:
                actual=('input_overflow',expected.expression,0)
            wanted=(expected.status,expected.expression,expected.steps)
            assert actual==wanted,(k,expression,fuel,actual,wanted)
            counts[actual[0]]+=1
            if (k+1)%100==0:
                print('V44 checked',k+1,dict(counts),flush=True)
        # Exercise the full tape and every supported fuel, including 16 active
        # contractions; sparse random trees do not reliably cover this boundary.
        full='I'
        for _ in range(6):full='@'+full+full
        for fuel in range(17):
            expected=evaluate(full,6,fuel)
            result=machine.run(full,fuel)
            assert (result.status,result.expression,result.steps)==(
                expected.status,expected.expression,expected.steps)
    print('V44 depth-6 16-round differential passed:',sum(counts.values()),dict(counts))
    print('Full 127-node tree: all 17 fuel values passed')
    return counts
if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--font',default='build/v44-depth6-r16.ttf')
    parser.add_argument('--samples',type=int,default=1000)
    a=parser.parse_args()
    run(a.font,a.samples)
