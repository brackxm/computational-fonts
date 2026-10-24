# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Check real HarfBuzz shaping, word boundaries, colour tables and fallback glyphs."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from fontTools.ttLib import TTFont

from build import build_font, glyph_name, spellings

HERE = Path(__file__).resolve().parent
FONT = HERE / 'first-words-font.ttf'
MANIFEST = json.loads((HERE / 'manifest.json').read_text())


def shape(text, *, enabled=True, font=FONT):
    output = subprocess.check_output(['hb-shape', str(font), text, '--output-format=json',
                                      '--features=liga=' + ('1' if enabled else '0')], text=True)
    return json.loads(output)


def pictures(shaped):
    return [item['g'] for item in shaped if item['g'].startswith('picture_')]


@unittest.skipUnless(shutil.which('hb-shape'), 'Install hb-shape (HarfBuzz) to test shaping')
class PictureFontTests(unittest.TestCase):
    def test_all_words_and_case_variants(self):
        for drawing in MANIFEST['drawings']:
            label = drawing['label']
            mixed = ''.join(c.upper() if i % 2 else c for i,c in enumerate(label))
            for text in {label, label.upper(), label.title(), mixed}:
                with self.subTest(text=text):
                    result = shape(text)
                    self.assertEqual([g['g'] for g in result], [glyph_name(drawing)])
                    self.assertEqual(result[0]['ax'], 2294)

    def test_compounds_and_punctuation(self):
        for drawing in MANIFEST['drawings']:
            for text in spellings(drawing):
                with self.subTest(text=text):
                    self.assertEqual(pictures(shape(text)), [glyph_name(drawing)])
            with self.subTest(word=drawing['label']):
                self.assertEqual(pictures(shape('("'+drawing['label']+'"),')), [glyph_name(drawing)])

    def test_substrings_and_joined_words_stay_text(self):
        texts = ('caterpillar', 'concatenate', 'catapult', 'bobcat', 'hotdog', 'dogma',
                 'pineapples', 'applepie', 'backbone', 'toothpaste', 'sunny', 'sunflower',
                 'starfish', 'earring', 'hearty', 'trainer', 'handbook', 'bookcase',
                 'treehouse', 'bluebird', 'sheepskin', 'catdog', 'ice creamer', 'teddy bears',
                 'écat', 'caté', 'cat\u0301', 'cat1', '1cat', '_cat', 'cat_', "cat's", 'cat’s',
                 'hot-dog', 'cat-dog', 'cat‑dog', 'cat‐dog')
        for text in texts:
            with self.subTest(text=text):
                self.assertEqual(pictures(shape(text)), [])
                self.assertEqual(shape(text), shape(text, enabled=False))

    def test_mixed_sentence_and_disabled_ligatures(self):
        source = 'The cat is in the house. Apple, banana! (ice cream) teddy-bear'
        self.assertEqual(pictures(shape(source)),
                         ['picture_cat','picture_house','picture_apple','picture_banana',
                          'picture_ice_cream','picture_teddy_bear'])
        self.assertEqual(pictures(shape(source, enabled=False)), [])
        # Unknown input retains its original uppercase/lowercase glyphs.
        with TTFont(FONT) as font:
            cmap = font.getBestCmap()
        self.assertEqual([i['g'] for i in shape('Unknown TEXT')], [cmap[ord(c)] for c in 'Unknown TEXT'])

    def test_colour_and_monochrome_are_vector_geometry(self):
        with TTFont(FONT) as font:
            self.assertEqual(font['COLR'].version, 0)
            self.assertEqual(len(font['COLR'].ColorLayers), 100)
            self.assertEqual(len(font['CPAL'].palettes[0]), 16)
            for tag in ('SVG ', 'sbix', 'CBDT', 'CBLC'):
                self.assertNotIn(tag, font)
            for drawing in MANIFEST['drawings']:
                target = glyph_name(drawing)
                self.assertGreater(font['glyf'][target].numberOfContours, 0)
                for layer in font['COLR'].ColorLayers[target]:
                    self.assertGreater(font['glyf'][layer.name].numberOfContours, 0)
            self.assertEqual(font['OS/2'].fsType, 0)
            self.assertIn('Google', font['name'].getDebugName(0))
            self.assertIn('Apache', font['name'].getDebugName(13))
            self.assertEqual(font['name'].getDebugName(1), 'First Words Pictures')

    def test_webfont_and_reproducible_build(self):
        with TTFont(FONT.with_suffix('.woff2')) as web, TTFont(FONT) as desktop:
            self.assertEqual(web['GSUB'].compile(web), desktop['GSUB'].compile(desktop))
            self.assertEqual(web['COLR'].compile(web), desktop['COLR'].compile(desktop))
        with tempfile.TemporaryDirectory() as directory:
            rebuilt = Path(directory) / 'pictures.ttf'
            build_font(rebuilt)
            self.assertEqual(rebuilt.read_bytes(), FONT.read_bytes())


if __name__ == '__main__':
    unittest.main()
