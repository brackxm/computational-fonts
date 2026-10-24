# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Check column-aware sharing against independently enumerated comparisons."""
import json
from pathlib import Path
import random
import shutil
import subprocess
import tempfile
import unittest
from lower import column_levels


class LowerTests(unittest.TestCase):
    def test_column_levels_preserve_every_cross_column_comparison(self):
        rng = random.Random(20261024)
        for _ in range(100):
            policy = list(range(42)); rng.shuffle(policy)
            levels = column_levels(policy)
            for a in range(42):
                for b in range(42):
                    if a//6 != b//6:
                        self.assertEqual(policy[a] < policy[b], levels[a] < levels[b])
        center = list(range(42))
        self.assertEqual(column_levels(center), [col for col in range(7) for _ in range(6)])

    def test_grouping_preserves_cross_column_orders_without_cycles(self):
        compiler = shutil.which('clang++') or shutil.which('c++')
        if not compiler:
            self.skipTest('C++17 compiler required for the offline grouper')
        rng = random.Random(6124)
        chains = [[0, 1, 6], [1, 0, 6], [6, 0]]
        chains += [rng.sample(range(18), rng.randint(3, 18)) for _ in range(200)]
        tape = str(len(chains))+'\n'+''.join(str(len(c))+' '+ ' '.join(map(str,c))+'\n' for c in chains)
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory)/'group'
            subprocess.run([compiler, '-O2', '-std=c++17', str(Path(__file__).with_name('group_policies.cpp')), '-o', str(binary)], check=True)
            result = subprocess.run([str(binary)], input=tape, text=True, capture_output=True, check=True)
        groups = json.loads(result.stdout)
        self.assertEqual(groups['assignments'][0], groups['assignments'][1])
        self.assertNotEqual(groups['assignments'][0], groups['assignments'][2])
        for chain, group in zip(chains, groups['assignments']):
            policy = column_levels(groups['policies'][group])
            for i, a in enumerate(chain):
                for b in chain[i+1:]:
                    if a//6 != b//6:
                        self.assertLess(policy[a], policy[b])


if __name__ == '__main__':
    unittest.main()
