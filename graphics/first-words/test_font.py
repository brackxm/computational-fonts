# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Check real HarfBuzz shaping, word boundaries, colour tables and fallback glyphs."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from zipfile import ZipFile

from fontTools.ttLib import TTFont

from build import build_font, glyph_name, spellings
from word_labels import validate_labels

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
            for label in [drawing['label'], *drawing['aliases']]:
                mixed = ''.join(c.upper() if i % 2 else c for i,c in enumerate(label))
                for text in {label, label.upper(), label.title(), mixed}:
                    with self.subTest(text=text):
                        result = shape(text)
                        self.assertEqual([g['g'] for g in result], [glyph_name(drawing, label)])
                        self.assertEqual(result[0]['ax'], 2294)

    def test_compounds_and_punctuation(self):
        for drawing in MANIFEST['drawings']:
            for text in spellings(drawing):
                with self.subTest(text=text):
                    self.assertEqual(pictures(shape(text)), [glyph_name(drawing, text)])
            with self.subTest(word=drawing['label']):
                self.assertEqual(pictures(shape('("'+drawing['label']+'"),')), [glyph_name(drawing)])

    def test_substrings_and_joined_words_stay_text(self):
        texts = ('caterpillar', 'concatenate', 'catapult', 'bobcat', 'hotdog', 'dogma',
                 'applepie', 'backbone', 'toothpaste', 'sunny', 'sunflower',
                 'starfish', 'earring', 'hearty', 'trainer', 'handbook', 'bookcase',
                 'treehouse', 'bluebird', 'sheepskin', 'catdog', 'ice creamer', 'teddybearlike',
                 'écat', 'caté', 'cat\u0301', 'cat1', '1cat', '_cat', 'cat_', "cat's", 'cat’s',
                 'hot-dog', 'cat-dog', 'cat‑dog', 'cat‐dog', 'basketball', 'whalebone',
                 'soapbox', 'SOaPbox', 'CATALOG', 'bathroom', 'cornbread', 'cornflower',
                 "panda's", 'motorcyclist', 'phonebook', 'sawdust', 'capstone',
                 'Antelope', 'pc1', 'fireenginex')
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

    def test_alternate_words_in_sentences_and_overlapping_phrases(self):
        source = 'A couch, refrigerator, bike and teeth. Table lamp; bar of soap; ice creams.'
        self.assertEqual(pictures(shape(source)),
                         ['picture_sofa', 'picture_fridge', 'picture_bicycle', 'picture_tooth_plural',
                          'picture_lamp', 'picture_soap', 'picture_ice_cream_plural'])
        self.assertEqual(pictures(shape(source, enabled=False)), [])
        self.assertEqual(pictures(shape('TABLE LAMPshade; TEDDY BEARlike; SOAP BARometer')),
                         ['picture_table', 'picture_teddy_bear', 'picture_soap'])
        with TTFont(FONT) as font:
            cmap = font.getBestCmap()
        self.assertEqual([g['g'] for g in shape('TABLE LAMPshade')],
                         ['picture_table', *[cmap[ord(c)] for c in ' LAMPshade']])

    def test_conflicting_aliases_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Ambiguous label'):
            validate_labels([dict(id='bear', label='bear', aliases=['toy bear']),
                             dict(id='toy', label='toy', aliases=['toybear'])])
        with self.assertRaisesRegex(ValueError, 'Plural labels must be existing labels'):
            validate_labels([dict(id='cat', label='cat', aliases=[], plurals=['cats'])])

    def test_plural_routing_and_exceptions(self):
        self.assertEqual(pictures(shape('apple apples cat cats chair chairs mouse mice foot feet tooth teeth')),
                         ['picture_apple', 'picture_apple_plural', 'picture_cat', 'picture_cat_plural',
                          'picture_chair', 'picture_chair_plural', 'picture_mouse', 'picture_mouse_plural',
                          'picture_foot', 'picture_foot_plural', 'picture_tooth', 'picture_tooth_plural'])
        self.assertEqual(pictures(shape('fish sheep grapes peas blueberries pancakes popcorn bread cheese trousers pants scissors')),
                         ['picture_fish', 'picture_sheep', 'picture_grapes', 'picture_peas', 'picture_blueberry',
                          'picture_pancake', 'picture_popcorn', 'picture_bread', 'picture_cheese',
                          'picture_trousers', 'picture_trousers', 'picture_scissors'])
        self.assertEqual(pictures(shape('fishes loaves cheese wedges cacti bars of soap')),
                         ['picture_fish_plural', 'picture_bread_plural', 'picture_cheese_plural',
                          'picture_cactus_plural', 'picture_soap_plural'])

    def test_plural_geometry_repeats_the_same_colours_and_advance(self):
        with TTFont(FONT) as font:
            for drawing in MANIFEST['drawings']:
                if not drawing['plurals']:
                    continue
                single, plural = glyph_name(drawing), glyph_name(drawing, plural=True)
                base_layers = font['COLR'].ColorLayers[single]
                repeated = font['COLR'].ColorLayers[plural]
                self.assertEqual([l.colorID for l in repeated], [l.colorID for l in base_layers]*2)
                self.assertEqual(font['hmtx'][single][0], font['hmtx'][plural][0])
                self.assertGreater(font['glyf'][plural].numberOfContours, 0)

    def test_colour_and_monochrome_are_vector_geometry(self):
        with TTFont(FONT) as font:
            self.assertEqual(font['COLR'].version, 0)
            self.assertEqual(len(font['COLR'].ColorLayers), MANIFEST['count']+MANIFEST['plural_count'])
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

    def test_font_bundle_contains_current_outputs_and_notices(self):
        with ZipFile(HERE / 'first-words-fonts.zip') as archive:
            for name in ('first-words-font.ttf', 'first-words-font.woff2', 'first-words-font.json',
                         'words.txt', 'aliases.tsv', 'FONT_LICENSE.txt', 'FONT_NOTICE.txt',
                         'FONT_README.txt', 'LICENSE.txt', 'NOTICE.txt'):
                self.assertEqual(archive.read(name), (HERE / name).read_bytes(), name)


if __name__ == '__main__':
    unittest.main()
