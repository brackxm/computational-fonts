"""V37: adversarial cross-configuration differential and protocol tests.

Every evaluation is executed by the generated font through real HarfBuzz.
The reference is used only for independent comparison.
"""
import argparse
import json
import random
from collections import Counter
from pathlib import Path
from dataclasses import replace

from .runtime import Machine, MachineError, InputOverflow
from .reference import evaluate
from .syntax import App, Leaf, prefix


def run(font='build/ski-tree-small.ttf', seed=370037, samples=1500):
    rng = random.Random(seed)
    outcomes = Counter()
    with Machine(font) as machine:
        def compare(source, fuel):
            reference = evaluate(source, machine.depth, fuel)
            try:
                actual = machine.run(source, fuel)
            except InputOverflow:
                assert reference.status == 'input_overflow', (source, fuel, reference)
                outcomes['input_overflow'] += 1
                return
            assert (actual.status, actual.expression, actual.steps) == (
                reference.status, reference.expression, reference.steps
            ), (source, fuel, actual, reference)
            outcomes[actual.status] += 1
            assert len(actual.glyphs) == machine.meta['tape_glyphs']
            assert machine.decode(actual.glyphs, fuel) == actual
            for corrupted in (
                ('seek',) + actual.glyphs[1:],
                actual.glyphs[:-1] + ('f9999',),
                actual.glyphs[:1] + ('n0_E',) + actual.glyphs[2:],
                actual.glyphs[:-2],
            ):
                try:
                    machine.decode(corrupted, fuel)
                except MachineError:
                    pass
                else:
                    # Root substitution is harmless only for a truly empty tree,
                    # which valid SKI input never is.
                    raise AssertionError(('corrupted output accepted', source, corrupted))

        # Force compound operands in all three S positions, including discarded
        # redexes under K and partial applications.
        fixed = [
            'I a', 'K a b', 'S K K a', 'K a (S I I (S I I))',
            'S (I a) (K b c) (I c)', 'S (K a) (I b) (K c d)',
            'S a b (K c d)', 'S K K (I a)', 'S K K (S K K a)',
            'I', 'K', 'S', 'K a', 'S K', 'S K K',
        ]
        for source in fixed:
            for fuel in range(machine.rounds + 1):
                compare(source, fuel)

        def tree(depth):
            if not depth or rng.random() < .4:
                return Leaf(rng.choice('SKIabcde'))
            return App(tree(depth-1), tree(depth-1))

        for _ in range(samples):
            expression = prefix(tree(machine.depth))
            compare(expression, rng.randrange(machine.rounds + 1))

        # Every saturated S application whose operands are atoms (including
        # combinators) under a capacity that permits it.
        for x in 'SKIabc':
            for y in 'SKIabc':
                for z in 'SKIabc':
                    compare(f'S {x} {y} {z}', 1)

        # Explicit API validation and lifecycle handling.
        for invalid in (-1, machine.rounds+1, 1.5, True):
            try:
                machine.run('a', invalid)
            except ValueError:
                pass
            else:
                raise AssertionError(('accepted invalid fuel', invalid))
    try:
        machine.run('a', 0)
    except MachineError:
        pass
    else:
        raise AssertionError('closed HarfBuzz font remained usable')
    report = {'font': str(font), 'seed': seed, 'cases': sum(outcomes.values()), 'outcomes': dict(outcomes)}
    print(json.dumps(report, indent=2))
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--font', default='build/ski-tree-small.ttf')
    p.add_argument('--samples', type=int, default=1500)
    a = p.parse_args()
    run(a.font, samples=a.samples)
