# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Real-HarfBuzz equivalence across lookup pruning and profiler smoke checks."""
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from fontTools.ttLib import TTFont

from .build import build
from .config import ROOT
from .profile import profile
from .reference import evaluate
from .runtime import InputOverflow, Machine
from .syntax import App, Leaf, prefix
from .visible import build_visible, serialize


class OptimizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='ski-pruning-tests-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.folder = Path(cls.temporary.name)
        cls.original, cls.optimized = cls.folder / 'original.ttf', cls.folder / 'optimized.ttf'
        build(cls.original, 4, 8, optimize=False)
        build(cls.optimized, 4, 8)

    def test_pruning_preserves_protocol_tables_and_unique_schedule(self):
        with TTFont(self.original) as original, TTFont(self.optimized) as optimized:
            self.assertLess(optimized['GSUB'].table.LookupList.LookupCount,
                            original['GSUB'].table.LookupList.LookupCount)
            self.assertLess(self.optimized.stat().st_size, self.original.stat().st_size)
            self.assertEqual(original.getGlyphOrder(), optimized.getGlyphOrder())
            for table in original.keys():
                if table not in ('GlyphOrder', 'GSUB', 'head'):
                    self.assertEqual(original.getTableData(table), optimized.getTableData(table), table)
            indices = optimized['GSUB'].table.FeatureList.FeatureRecord[0].Feature.LookupListIndex
            self.assertEqual(len(indices), len(set(indices)))
            self.assertEqual(len(indices), 8 * 69 + 2)

    def test_original_v42_differential_corpus(self):
        rng = random.Random(42042)
        def tree(depth):
            if not depth or rng.random() < .55:
                return Leaf(rng.choice('SKIabcde'))
            return App(tree(depth - 1), tree(depth - 1))
        expressions = ['I a', 'K a b', 'S K K a', 'S a b (K c d)',
                       'S (I a) b (I c)', 'K a ((S I I) (S I I))']
        expressions.extend(prefix(tree(4)) for _ in range(200))
        with Machine(self.original) as original, Machine(self.optimized) as optimized:
            for source in expressions:
                for fuel in (0, 1, 2, 4, 8):
                    expected = evaluate(source, 4, fuel)
                    if expected.status == 'input_overflow':
                        for machine in (original, optimized):
                            with self.assertRaises(InputOverflow):
                                machine.run(source, fuel)
                        continue
                    left, right = original.run(source, fuel), optimized.run(source, fuel)
                    self.assertEqual(left, right, (source, fuel))
                    self.assertEqual((right.status, right.expression, right.steps),
                                     (expected.status, expected.expression, expected.steps))

    def test_visible_pruning_preserves_raw_output(self):
        plain, pruned = self.folder / 'plain-visible.ttf', self.folder / 'pruned-visible.ttf'
        build_visible(self.original, plain, optimize=False)
        build_visible(self.optimized, pruned)
        from .runtime import HarfBuzz
        left, right = HarfBuzz(plain), HarfBuzz(pruned)
        try:
            for source in ('I a', 'S K K a', 'S a b (K c d)',
                           'K a (S I I (S I I))', 'S I I (S I I)'):
                for fuel in (0, 1, 8):
                    text = serialize(source, fuel, 4, 8)
                    self.assertEqual(left.shape(text, {'rlig': 1}), right.shape(text, {'rlig': 1}))
            with TTFont(plain) as a, TTFont(pruned) as b:
                self.assertEqual(a.getBestCmap(), b.getBestCmap())
                self.assertEqual(a.getTableData('GDEF'), b.getTableData('GDEF'))
                self.assertLess(b['GSUB'].table.LookupList.LookupCount, a['GSUB'].table.LookupList.LookupCount)
        finally:
            left.close()
            right.close()

    def test_profile_and_benchmark_commands_from_another_directory(self):
        for samples, warmups in ((1, 0), (True, 0), (2, -1)):
            with self.assertRaises(ValueError):
                profile(self.optimized, samples=samples, warmups=warmups)
        for script, args in (
                ('profile_font.py', ['--font', str(self.optimized)]),
                ('benchmark.py', ['--depth', '3', '--rounds', '1'])):
            result = subprocess.run([sys.executable, str(ROOT / script), *args,
                                     '--samples', '2', '--warmups', '0'], cwd=self.folder,
                                    capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            profiles = report.get('configurations', [report])
            for item in profiles:
                self.assertEqual(item['samples'], 2)
                self.assertTrue(item['harfbuzz'])
                self.assertEqual(len(item['font_sha256']), 64)
                self.assertEqual(item['measurements']['I a']['steps'], 1)
                self.assertGreaterEqual(item['measurements']['I a']['p95_ms'],
                                        item['measurements']['I a']['median_ms'])
            if 'configurations' in report:
                self.assertEqual([p['optimized'] for p in profiles], [False, True])
                self.assertLess(profiles[1]['lookups'], profiles[0]['lookups'])


if __name__ == '__main__':
    unittest.main()
