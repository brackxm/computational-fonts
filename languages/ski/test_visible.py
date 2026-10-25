# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""One-call tests of the font-side ASCII parser, evaluator and rendered output."""
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from fontTools.ttLib import TTFont
from bounded.build import build
from bounded.config import ROOT, DEFAULT_FONT
from bounded.outputs import font_artifacts
from bounded.reference import evaluate
from bounded.runtime import HarfBuzz
from bounded.syntax import App, Leaf, parse, prefix
from bounded.visible import build_visible, serialize, DISPLAY_FONT, DEFAULT_BASE


def parentheses(tree):
    if isinstance(tree, Leaf):
        return tree.value
    return '(' + parentheses(tree.left) + ' ' + parentheses(tree.right) + ')'


class VisibleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='ski-visible-tests-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.folder = Path(cls.temporary.name)
        machine = cls.folder / 'machine.ttf'
        build(machine, 3, 4)
        compact = cls.folder / 'visible.ttf'
        cls.compact_meta = build_visible(machine, compact)
        cls.compact = HarfBuzz(compact)
        cls.addClassCleanup(cls.compact.close)
        cls.bundled_meta = json.loads(DISPLAY_FONT.with_suffix('.json').read_text())
        cls.bundled = HarfBuzz(DISPLAY_FONT)
        cls.addClassCleanup(cls.bundled.close)

    def actual(self, text, compact=False):
        hb, meta = (self.compact, self.compact_meta) if compact else (self.bundled, self.bundled_meta)
        with patch.object(hb, 'shape', wraps=hb.shape) as shaping:
            with patch('bounded.reference.step', side_effect=AssertionError('host reducer called')):
                glyphs = hb.shape(text, {'rlig': 1, 'calt': 0})
        self.assertEqual(shaping.call_count, 1)
        return ''.join(meta['display'].get(g, '') for g in glyphs)

    def compare(self, source, fuel, compact=False):
        depth, rounds = (3, 4) if compact else (5, 32)
        expected = evaluate(source, depth, fuel)
        text = serialize(source, fuel, depth, rounds)
        label = {'normal': 'NORMAL', 'budget': 'STEP LIMIT', 'overflow': 'DEPTH LIMIT'}[expected.status]
        wanted = f'{label}  {parentheses(parse(expected.expression))}  [fuel {fuel-expected.steps}]'
        self.assertEqual(self.actual(text, compact), wanted, (source, fuel))

    def test_compact_differential(self):
        small = {0: list('SKIab')}
        for count in (1, 2):
            small[count] = ['@' + l + r for k in range(count)
                            for l in small[k] for r in small[count-k-1]]
        count = 0
        for trees in small.values():
            for tree in trees:
                for fuel in range(5):
                    self.compare(tree, fuel, compact=True)
                    count += 1
        rng = random.Random(20261016)
        def tree(depth):
            if not depth or rng.random() < .35:
                return Leaf(rng.choice('SKIabcdefghijklmnopqrstuvwxyz'))
            return App(tree(depth-1), tree(depth-1))
        for _ in range(200):
            self.compare(prefix(tree(3)), rng.randrange(5), compact=True)
            count += 1
        print('Visible compact differential cases:', count, flush=True)

    def test_bundled_semantics_and_capacity(self):
        for source in ('I a', 'K a b', 'S K K a', 'S (I a) b (I c)',
                       'K a (S I I (S I I))', 'S a b (K c d)', 'S (I a)',
                       'S a b (a (a (a (a a))))', 'S I I (S I I)'):
            for fuel in (0, 1, 2, 32):
                self.compare(source, fuel)
        for atom in 'SKIabcdefghijklmnopqrstuvwxyz':
            self.compare('I ' + atom, 32)
        full = 'I'
        for _ in range(5):
            full = '@' + full + full
        for fuel in (0, 1, 16, 31, 32):
            self.compare(full, fuel)
        long_case = '@@@@@SI@KII@@@IK@II@@II@SS@@@@II@SI@@II@II@@@SI@IS@@II@II'
        self.compare(long_case, 32)

    def test_raw_protocol_errors_and_disabled_feature(self):
        for text in ('SKI;@I!', 'SKI;ab!', 'SKI;@Ia!!', 'SKI;@Ia!a', 'SKI;!',
                     'SKI;@Ia', 'SKI;(', 'SKI33;@Ia!', 'I a', 'junk', 'SKI;é!'):
            self.assertEqual(self.actual(text + '.' * 191), 'SYNTAX ERROR', text)
        self.assertEqual(self.actual('SKI;' + '@I' * 6 + 'a!' + '.' * 191), 'INPUT TOO DEEP')
        self.assertEqual(self.actual('SKI; @ I a !' + '.' * 191), 'NORMAL  a  [fuel 31]')
        text = serialize('I a')
        glyphs = self.bundled.shape(text, {'rlig': 0, 'calt': 0})
        self.assertFalse(any(g.startswith('ski.output') or g.startswith('ski.status') for g in glyphs))

    def test_machine_aliases_are_rejected_without_modification(self):
        machine = self.folder / 'machine.ttf'
        before = machine.read_bytes()
        hardlink, symlink = self.folder / 'hardlink.ttf', self.folder / 'symlink.ttf'
        os.link(machine, hardlink)
        symlink.symlink_to(machine)
        for output in (machine, hardlink, symlink):
            with self.subTest(output=output), self.assertRaisesRegex(ValueError, 'differ'):
                build_visible(machine, output)
            self.assertEqual(machine.read_bytes(), before)
            if output != machine:
                self.assertFalse(output.with_suffix('.json').exists())

    def test_all_visible_outputs_preserve_input_artifacts(self):
        source_machine = self.folder / 'machine.ttf'
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            machine = folder / 'machine.ttf'
            for source, target in zip(font_artifacts(source_machine), font_artifacts(machine)):
                target.write_bytes(source.read_bytes())
            base = folder / 'base.ttf'
            base.write_bytes(DEFAULT_BASE.read_bytes())
            outputs = [machine.with_suffix(suffix) for suffix in ('.otf', '.json', '.fea')]
            # Include aliases between every output and every source artifact.
            for index, source in enumerate((*font_artifacts(machine), base)):
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
            with patch('bounded.visible.DEFAULT_BASE', base):
                for output in outputs:
                    with self.subTest(output=output), self.assertRaisesRegex(ValueError, 'differ'):
                        build_visible(machine, output)
            self.assertEqual({p: p.read_bytes() for p in folder.iterdir()}, before)

    def test_custom_visible_output_and_bundled_protection(self):
        machine = self.folder / 'machine.ttf'
        before = DISPLAY_FONT.read_bytes()
        alias = self.folder / 'display-alias.ttf'
        os.link(DISPLAY_FONT, alias)
        for output in (DISPLAY_FONT, alias):
            with self.subTest(output=output), self.assertRaisesRegex(ValueError, 'different path'):
                build_visible(machine, output)
            self.assertEqual(DISPLAY_FONT.read_bytes(), before)
        custom = self.folder / 'cli-visible.ttf'
        result = subprocess.run([sys.executable, str(ROOT / 'build.py'), '--visible',
                                 '--depth', '3', '--rounds', '4', '--output', str(custom)],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        meta = json.loads(custom.with_suffix('.json').read_text())
        hb = HarfBuzz(custom)
        try:
            glyphs = hb.shape(serialize('I a', 4, 3, 4), {'rlig': 1, 'calt': 0})
            self.assertEqual(''.join(meta['display'].get(g, '') for g in glyphs), 'NORMAL  a  [fuel 3]')
        finally:
            hb.close()

    def test_metadata_source_protection_and_reproducibility(self):
        with TTFont(DISPLAY_FONT) as font:
            self.assertEqual(font['name'].getBestFamilyName(), 'SKI Evaluator')
            self.assertEqual(font['OS/2'].fsType, 0)
            self.assertIn('Google', font['name'].getDebugName(0))
            self.assertIn('Michael Brackx', font['name'].getDebugName(0))
            self.assertIn('Apache', font['name'].getDebugName(13))
            self.assertGreater(len(font['glyf']['ski.output0_a'].getCoordinates(font['glyf'])[0]), 0)
            self.assertEqual(font['GSUB'].table.FeatureList.FeatureRecord[0].FeatureTag, 'rlig')
        before = hashlib.sha256(DEFAULT_BASE.read_bytes()).hexdigest()
        with self.assertRaises(ValueError):
            build_visible(DEFAULT_FONT, DEFAULT_BASE)
        self.assertEqual(before, hashlib.sha256(DEFAULT_BASE.read_bytes()).hexdigest())
        machine, output = self.folder / 'repro-machine.ttf', self.folder / 'repro.ttf'
        build(machine, 5, 32)
        build_visible(machine, output)
        self.assertEqual(output.read_bytes(), DISPLAY_FONT.read_bytes())
        self.assertEqual(output.with_suffix('.json').read_bytes(), DISPLAY_FONT.with_suffix('.json').read_bytes())

    def test_specimen_embeds_current_font_and_runs_examples(self):
        namespace = {'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0'}
        with ZipFile(ROOT / 'ski.odt') as document:
            self.assertEqual(document.read('Fonts/computational.ttf'), DISPLAY_FONT.read_bytes())
            content = ET.fromstring(document.read('content.xml'))
            for paragraph in content.findall('.//text:p', namespace):
                if paragraph.attrib.get('{urn:oasis:names:tc:opendocument:xmlns:text:1.0}style-name') == 'Rendered':
                    text = ''.join(paragraph.itertext())
                    self.assertIn('!'+'.'*191, text)
                    self.assertTrue(self.actual(text).startswith(('NORMAL', 'STEP LIMIT')))


def check_depth_six_visible(machine, output):
    """Exercise the largest visible build with the required pure-Python serializer."""
    with patch('fontTools.ttLib.tables.otBase.have_uharfbuzz', False):
        meta = build_visible(machine, output)
    hb, cases = HarfBuzz(output), 0

    def actual(program):
        return ''.join(meta['display'].get(g, '')
                       for g in hb.shape(program, {'rlig': 1, 'calt': 0}))

    def compare(source, fuel):
        nonlocal cases
        expected = evaluate(source, 6, fuel)
        label = {'normal': 'NORMAL', 'budget': 'STEP LIMIT', 'overflow': 'DEPTH LIMIT'}[expected.status]
        wanted = f'{label}  {parentheses(parse(expected.expression))}  [fuel {fuel-expected.steps}]'
        got = actual(serialize(source, fuel, 6, 16))
        assert got == wanted, (source, fuel, wanted, got)
        cases += 1

    try:
        full = 'I'
        for _ in range(6):
            full = '@' + full + full
        for fuel in range(17):
            compare(full, fuel)
        for source in ('I a', 'K a b', 'S K K a', 'S (I a) b (I c)',
                       'S (a b) (c d) (e (f g))', 'K a (S I I (S I I))',
                       'S (I a)', 'S I I (S I I)', 'S a b (a (a (a (a (a a)))))'):
            for fuel in (0, 1, 8, 16):
                compare(source, fuel)
        for atom in 'SKIabcdefghijklmnopqrstuvwxyz':
            compare('I ' + atom, 16)
        rng = random.Random(20261017)

        def tree(depth):
            if not depth or rng.random() < .25:
                return Leaf(rng.choice('SKIabcdefghijklmnopqrstuvwxyz'))
            return App(tree(depth-1), tree(depth-1))

        for _ in range(100):
            compare(prefix(tree(6)), rng.randrange(17))
        for program, wanted in (('SKI;@I!', 'SYNTAX ERROR'),
                                ('SKI17;@Ia!', 'SYNTAX ERROR'),
                                ('SKI;' + '@I' * 7 + 'a!', 'INPUT TOO DEEP')):
            got = actual(program + '.' * 383)
            assert got == wanted, (program, wanted, got)
            cases += 1
    finally:
        hb.close()
    print('Visible depth-six regression cases:', cases, flush=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
