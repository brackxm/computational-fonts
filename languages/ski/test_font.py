# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0

"""HarfBuzz-backed regression gate; --quick skips depth-six, --full adds the corpus."""
import argparse
import contextlib
import importlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from fontTools.ttLib import TTFont
from bounded.build import build
from bounded.check import check
from bounded.config import DEFAULT_FONT, ROOT
from bounded.outputs import font_artifacts
from bounded.runtime import Machine
from bounded.visible import DISPLAY_FONT
from bounded.test_protocol import ProtocolTests
from bounded.test_optimization import OptimizationTests
from bounded.test_v37 import run as adversarial
from bounded.test_v38 import run as alphabet_and_fuel
from bounded.test_v44 import run as depth_six
from test_visible import VisibleTests, check_depth_six_visible


class IntegrationTests(unittest.TestCase):
    def test_visible_outputs_cannot_replace_machine_artifacts(self):
        spec = importlib.util.spec_from_file_location('ski_builder', ROOT / 'build.py')
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        visible = importlib.import_module('bounded.visible')
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            bundled = folder / 'ski.ttf'
            for artifact in font_artifacts(bundled, timing=True):
                artifact.write_bytes(b'protected machine artifact')
            outputs = [*font_artifacts(bundled, timing=True), bundled.with_suffix('.otf')]
            for index, source in enumerate(font_artifacts(bundled, timing=True)):
                for suffix in ('.ttf', '.json', '.fea'):
                    for kind in ('hard', 'symbolic'):
                        output = folder / f'alias-{index}-{suffix[1:]}-{kind}.ttf'
                        alias = output if suffix == '.ttf' else output.with_suffix(suffix)
                        if kind == 'hard':
                            os.link(source, alias)
                        else:
                            alias.symlink_to(source)
                        outputs.append(output)
            before = {p: p.read_bytes() for p in folder.iterdir()}
            with patch.object(visible, 'DEFAULT_FONT', bundled), patch.object(
                    visible, 'TTFont', side_effect=AssertionError('font loading started')):
                with patch.object(builder, 'build') as machine_build, patch.object(
                        builder, 'build_visible') as visible_build:
                    for output in outputs:
                        with self.subTest(output=output):
                            with self.assertRaises(ValueError):
                                visible.build_visible(folder / 'missing.ttf', output)
                            for depth, rounds in ((3, 4), (5, 32)):
                                with patch.object(sys, 'argv', ['build.py', '--visible', '--output', str(output),
                                                               '--depth', str(depth), '--rounds', str(rounds)]):
                                    with contextlib.redirect_stderr(io.StringIO()):
                                        with self.assertRaises(SystemExit) as exit:
                                            builder.main()
                                    self.assertEqual(exit.exception.code, 2)
                    machine_build.assert_not_called()
                    visible_build.assert_not_called()
            self.assertEqual({p: p.read_bytes() for p in folder.iterdir()}, before)

    def test_machine_outputs_cannot_replace_visible_artifacts(self):
        spec = importlib.util.spec_from_file_location('ski_builder', ROOT / 'build.py')
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        machine_builder = importlib.import_module('bounded.build')
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            bundled = folder / 'bundled.ttf'
            for artifact in font_artifacts(bundled):
                artifact.write_bytes(b'protected visible artifact')
            outputs = [*font_artifacts(bundled), bundled.with_suffix('.otf')]
            # Any one of the four machine outputs can alias any protected file.
            for index, source in enumerate(font_artifacts(bundled)):
                for suffix in ('.ttf', '.json', '.fea', '.build.json'):
                    for kind in ('hard', 'symbolic'):
                        output = folder / f'alias-{index}-{suffix[1:]}-{kind}.ttf'
                        alias = output if suffix == '.ttf' else output.with_suffix(suffix)
                        if kind == 'hard':
                            os.link(source, alias)
                        else:
                            alias.symlink_to(source)
                        outputs.append(output)
            before = {p: p.read_bytes() for p in folder.iterdir()}
            with patch('bounded.outputs.DISPLAY_FONT', bundled), patch.object(
                    machine_builder, 'FontBuilder', side_effect=AssertionError('build started')):
                for output in outputs:
                    with self.subTest(output=output):
                        with self.assertRaises(ValueError):
                            builder.build_font(output, depth=3, rounds=4)
                        for entry in (builder, machine_builder):
                            with patch.object(sys, 'argv', ['build.py', '--output', str(output),
                                                           '--depth', '3', '--rounds', '4']):
                                with contextlib.redirect_stderr(io.StringIO()):
                                    with self.assertRaises(SystemExit) as exit:
                                        entry.main()
                                self.assertEqual(exit.exception.code, 2)
                # The root CLI must reject before it invokes even a mocked build.
                with patch.object(builder, 'build') as machine_build:
                    with patch.object(sys, 'argv', ['build.py', '--output', str(bundled)]):
                        with contextlib.redirect_stderr(io.StringIO()):
                            with self.assertRaises(SystemExit) as exit:
                                builder.main()
                        self.assertEqual(exit.exception.code, 2)
                    machine_build.assert_not_called()
            self.assertEqual({p: p.read_bytes() for p in folder.iterdir()}, before)

    def test_custom_bundled_builds_are_rejected_before_writing(self):
        spec = importlib.util.spec_from_file_location('ski_builder', ROOT / 'build.py')
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        with tempfile.TemporaryDirectory() as td:
            alias = Path(td) / 'bundled-alias.ttf'
            os.link(DISPLAY_FONT, alias)
            configurations = [[], ['--visible'], ['--visible', '--output', str(DISPLAY_FONT)],
                              ['--visible', '--output', str(DISPLAY_FONT.with_suffix('.otf'))],
                              ['--visible', '--output', str(alias)]]
            with patch.object(builder, 'build') as machine_build, patch.object(builder, 'build_visible') as visible_build:
                for options in configurations:
                    with self.subTest(options=options), patch.object(
                            sys, 'argv', ['build.py', *options, '--depth', '3', '--rounds', '4']):
                        with contextlib.redirect_stderr(io.StringIO()) as stderr:
                            with self.assertRaises(SystemExit) as exit:
                                builder.main()
                        self.assertEqual(exit.exception.code, 2)
                        self.assertIn('different path', stderr.getvalue())
                machine_build.assert_not_called()
                visible_build.assert_not_called()

    def test_bundled_font_metadata_and_tape(self):
        with TTFont(DEFAULT_FONT) as font:
            self.assertEqual(font['name'].getDebugName(1), 'SKI Bounded Tree')
            self.assertIn('Michael Brackx', font['name'].getDebugName(0))
            self.assertIn('Apache', font['name'].getDebugName(13))
            self.assertTrue(all(width == 0 for width, _ in font['hmtx'].metrics.values()))
            self.assertTrue(all(font['glyf'][name].numberOfContours == 0
                                for name in font.getGlyphOrder()))
        with Machine(DEFAULT_FONT) as machine:
            self.assertEqual((machine.depth, machine.rounds), (5, 32))
            full = 'I'
            for _ in range(5):
                full = '@' + full + full
            result = machine.run(full)
            self.assertEqual((result.status, result.expression, result.steps), ('normal', 'I', 31))

    def test_commands_from_another_directory(self):
        with tempfile.TemporaryDirectory() as td:
            def command(script, *args):
                return subprocess.run([sys.executable, str(ROOT / script), *args],
                                      cwd=td, text=True, capture_output=True, timeout=60)

            result = command('run.py', 'S (I a) b (I c)')
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual((data['status'], data['expression'], data['steps'], data['shaping_calls']),
                             ('normal', 'a c (b c)', 4, 1))
            result = command('run.py', 'I a', '--encode', '--fuel', '1')
            self.assertEqual(result.returncode, 0, result.stderr)
            with Machine(DEFAULT_FONT) as machine:
                self.assertEqual(result.stdout, machine.encode('I a', 1)[0])
            for args in (('I a', '--fuel', '33'), ('(',), ('@',)):
                result = command('run.py', *args)
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertEqual(json.loads(result.stderr)['status'], 'error')
            result = command('build.py', '--output', 'nested/custom.ttf', '--depth', '3', '--rounds', '1')
            self.assertEqual(result.returncode, 0, result.stderr)
            with Machine(Path(td) / 'nested/custom.ttf') as machine:
                result = machine.run('I a')
                self.assertEqual((result.status, result.expression, result.steps), ('normal', 'a', 1))
            result = command('build.py', '--output', 'bad/font.ttf', '--depth', '6', '--rounds', '17')
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertFalse((Path(td) / 'bad').exists())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--quick', action='store_true', help='skip the depth-six build and regression')
    mode.add_argument('--full', action='store_true', help='also run the 11,869-case default-font corpus')
    args = parser.parse_args()

    suite = unittest.TestSuite()
    for case in (ProtocolTests, IntegrationTests, VisibleTests, OptimizationTests):
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(case))
    if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():
        return 1
    with tempfile.TemporaryDirectory(prefix='ski-tests-') as td:
        small = Path(td) / 'small.ttf'
        build(small, 3, 4)
        adversarial(small)
        alphabet_and_fuel(small)
        if not args.quick:
            print('Building and checking depth 6 / 16 rounds', flush=True)
            large = Path(td) / 'depth6.ttf'
            build(large, 6, 16)
            depth_six(large)
            check_depth_six_visible(large, Path(td) / 'depth6-visible.ttf')
        if args.full:
            check(DEFAULT_FONT, ROOT / 'build')
    print('PASS: SKI regression gate', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
