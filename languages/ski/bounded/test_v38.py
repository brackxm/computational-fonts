"""V38: systematic alphabet polymorphism and fuel-prefix invariants.

All outputs are from one real HarfBuzz call per test; the independent
reference is used solely to check results.
"""
import argparse
import json
from collections import Counter
from .runtime import Machine, InputOverflow
from .reference import evaluate


def run(font='build/ski-tree-small.ttf'):
    counts=Counter()
    with Machine(font) as m:
        alphabet='SKIabcdefghijklmnopqrstuvwxyz'
        expressions=[]
        for a in alphabet:
            expressions.extend((f'I {a}',f'K {a} b',f'S K K {a}',f'K a (S I I {a})'))
        for a in alphabet:
            for b in alphabet:
                expressions.append(f'S {a} {b} (K c d)')
        # An explicit sequence of budgets checks that results are not accidentally
        # computed by repeatedly shaping the result in Python.
        expressions.extend(('S K K (S K K a)', 'S (I a) b (I c)',
                            'K a (S I I (S I I))', 'S (K a) (I b) (K c d)'))
        for expression in expressions:
            for fuel in range(m.rounds+1):
                expected=evaluate(expression,m.depth,fuel)
                try:
                    actual=m.run(expression,fuel)
                except InputOverflow:
                    assert expected.status=='input_overflow',(expression,fuel,expected)
                    counts['input_overflow']+=1
                    continue
                assert (actual.status,actual.expression,actual.steps)==(expected.status,expected.expression,expected.steps),(expression,fuel,actual,expected)
                counts[actual.status]+=1
        # At zero fuel, an already-normal expression must still report normal.
        for expression in ('a','I','K','S','K a','S K','S K K'):
            got=m.run(expression,0)
            assert got.status=='normal' and got.steps==0,(expression,got)
            counts['zero_fuel_normal']+=1
    report={'cases':sum(counts.values()),'outcomes':dict(counts),'font':str(font)}
    print(json.dumps(report,indent=2))
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--font',default='build/ski-tree-small.ttf');a=p.parse_args();run(a.font)
