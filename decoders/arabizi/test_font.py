# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Actual HarfBuzz checks of source preservation, joins and independent rows."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from fontTools.ttLib import TTFont
from build import BASE, CELL, MAX_TOKENS, TOKENS, WORDS, annotation_advances, build_font, token_name

HERE = Path(__file__).resolve().parent

@unittest.skipUnless(shutil.which('hb-shape'), 'hb-shape is required')
class ArabiziTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.fresh = build_font(Path(cls.temp.name) / 'fresh.ttf')
        with TTFont(BASE) as base:
            cls.source_advances = annotation_advances(base)

    def shape(self, text, path=None, features=None):
        args = ['hb-shape', str(path or HERE / 'arabizi-font.ttf'), '--text=' + text,
                '--output-format=json', '--direction=ltr', '--script=latn']
        if features:
            args.append('--features=' + features)
        return json.loads(subprocess.check_output(args, text=True))

    def test_every_token_keeps_exact_original_annotation(self):
        for spelling in TOKENS:
            with self.subTest(spelling=spelling):
                out = self.shape(spelling)
                self.assertEqual([g['g'] for g in out], [token_name(spelling) + '.isol', token_name(spelling) + '.top'])
                self.assertEqual(sum(g['ax'] for g in out), CELL)

    def test_arabic_reverses_but_source_stays_left_to_right(self):
        out = self.shape('ktbn')
        pen = 0
        arabic, annotation = [], []
        for g in out:
            (annotation if g['g'].endswith('.top') else arabic).append(pen + g['dx'])
            pen += g['ax']
        self.assertEqual(arabic, [3*CELL, 2*CELL, CELL, 0])
        self.check_compact_annotation('ktbn', out)
        self.assertEqual([g['g'].split('.')[-1] for g in out[::2]], ['init', 'medi', 'medi', 'fina'])

    def check_compact_annotation(self, source, out):
        """Check actual source outline origins against natural Latin advances."""
        top = [g for g in out if g['g'].endswith('.top')]
        spellings = [bytes.fromhex(g['g'][1:-4]).decode('ascii') for g in top]
        self.assertEqual(''.join(spellings), source)
        widths = [sum(self.source_advances[c] for c in s) for s in spellings]
        expected = (len(top) * CELL - sum(widths)) // 2
        pen = 0
        index = 0
        for g in out:
            if g['g'].endswith('.top'):
                outline_start = pen + g['dx'] - CELL + (CELL - widths[index]) // 2
                self.assertEqual(outline_start, expected)
                expected += widths[index]
                index += 1
            pen += g['ax']

    def test_proportional_annotations_with_digraphs_case_and_long_words(self):
        for source in ('3rby', '7byby', "WiiSH3'ktbn", 'b' * MAX_TOKENS):
            with self.subTest(source=source):
                out = self.shape(source)
                self.check_compact_annotation(source, out)
                arabic = [g for g in out if not g['g'].endswith('.top')]
                self.assertEqual([i * CELL + g['dx'] for i, g in enumerate(arabic)],
                                 list(reversed(range(0, len(arabic) * CELL, CELL))))
                self.assertEqual(sum(g['ax'] for g in out), len(arabic) * CELL)

    def test_non_joining_letters_and_word_boundaries(self):
        self.assertEqual([g['g'].split('.')[-1] for g in self.shape('brb')[::2]], ['init', 'fina', 'isol'])
        out = self.shape('b b')
        self.assertEqual(out[0]['g'], 't62.isol')
        self.assertEqual(out[-2]['g'], 't62.isol')
        self.assertTrue(all(g['dx'] == 0 for g in out))

    def test_all_common_words_and_complete_word_guards(self):
        for word in WORDS:
            self.assertEqual([g['g'] for g in self.shape(word)], ['word.' + word])
            for embedded in ('b' + word, word + 'b'):
                self.assertFalse(any(g['g'].startswith('word.') for g in self.shape(embedded)))
        self.assertEqual(self.shape('salam!')[0]['g'], 'word.salam')

    def test_maximum_word_and_overflow_recovery(self):
        at_limit = self.shape('b' * MAX_TOKENS)
        self.assertEqual(at_limit[0]['dx'], (MAX_TOKENS - 1)*CELL)
        for n in (MAX_TOKENS + 1, 64, 100):
            out = self.shape('b' * n + ' ktb')
            self.assertTrue(all(g['g'] == 't62.raw' for g in out[:n]))
            self.assertEqual(out[n+1]['g'], 't6b.init')

    def test_digits_punctuation_and_disabled_substitution(self):
        out = self.shape('3\' 7\' 9\'! 0')
        self.assertIn('t3327.isol', [g['g'] for g in out])
        self.assertIn('u0021', [g['g'] for g in out])
        self.assertIn('u0030', [g['g'] for g in out])
        self.assertTrue(all(g['g'].startswith('u') for g in self.shape('7abibi', features='rlig=0')))

    def test_fresh_font_matches_bundle(self):
        for text in ('7abibi', 'ktbn', '3\'b 7\'n', 'b'*33, 'salam!'):
            self.assertEqual(self.shape(text), self.shape(text, self.fresh))
        with TTFont(self.fresh) as font:
            self.assertEqual(font['name'].getDebugName(1), 'Arabizi Annotated')
            self.assertIn('SIL Open Font License', font['name'].getDebugName(13))
            self.assertEqual(font['OS/2'].fsType, 0)

    def test_base_cannot_be_overwritten(self):
        with self.assertRaises(ValueError):
            build_font(BASE)

if __name__ == '__main__':
    unittest.main()
