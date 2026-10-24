# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Corpus integrity, font geometry and native HarfBuzz differential checks."""
import hashlib
import itertools
import json
from pathlib import Path
import random
import shutil
import string
import subprocess
import sys
import tempfile
import unittest

from fontTools.ttLib import TTFont
from collect import collect
from model import CHARACTERS, MAX_INPUT, normalize, select_index

ROOT = Path(__file__).resolve().parent
SHAPER = shutil.which('hb-shape')


def all_poem_seeds(count):
    seeds = {}
    for chars in itertools.product(string.ascii_letters+string.digits+string.punctuation, repeat=2):
        text = ''.join(chars)
        seeds.setdefault(select_index(text, count), text)
    return seeds


class PoemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.poems = json.loads((ROOT/'poems.json').read_text())
        cls.manifest = json.loads((ROOT/'poem-oracle.json').read_text())
        cls.temp = tempfile.TemporaryDirectory(prefix='poem-font-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.fresh = Path(cls.temp.name)/'poem-oracle.ttf'
        subprocess.run([sys.executable, str(ROOT/'build.py'), '--output', str(cls.fresh)],
                       check=True, capture_output=True, timeout=600)

    def test_corpus_is_reproducible_complete_and_unique(self):
        poems, counts = collect()
        self.assertEqual(poems, self.poems)
        self.assertGreater(len(poems), 1221)
        self.assertEqual(len({p['id'] for p in poems}), len(poems))
        self.assertEqual(len({p['author'] for p in poems}), 16)
        for poem in poems:
            self.assertTrue(poem['title'].strip(), poem['id'])
            self.assertNotIn('\n', poem['title'], poem['id'])
            self.assertEqual(sum(bool(s.strip()) for s in poem['text'].splitlines()), poem['line_count'])
            self.assertLessEqual(poem['line_count'], 16)
            self.assertLessEqual(len(poem['text'].split()), 120)
            self.assertNotIn('<', poem['text'])
            self.assertNotIn('>', poem['text'])
        known = {p['id']: p for p in poems}
        self.assertEqual(known['stevenson-rain']['line_count'], 4)
        self.assertTrue(known['stevenson-rain']['text'].endswith('And on the ships at sea.'))
        self.assertEqual(known['dunbar-retort']['line_count'], 10)
        self.assertTrue(known['dunbar-retort']['text'].endswith('"Thou art worse than a fool, O head!"'))
        self.assertEqual(known['millay-id00007']['text'],
            'My candle burns at both ends;\nIt will not last the night;\n'
            'But ah, my foes, and oh, my friends—\nIt gives a lovely light!')
        self.assertEqual(known['housman-XIII']['line_count'], 16)
        self.assertEqual(known['shakespeare-XVIII']['line_count'], 14)
        self.assertTrue(known['shakespeare-XVIII']['text'].endswith(
            'So long lives this, and this gives life to thee.'))
        self.assertEqual(counts['shakespeare']['complete_poems'], 154)
        self.assertEqual(known['crapsey-id00065']['text'],
            "Listen . . .\nWith faint dry sound,\nLike steps of passing ghosts,\n"
            "The leaves, frost-crisp'd, break from the trees\nAnd fall.")
        self.assertEqual(known['mckay-AMERICA']['line_count'], 14)
        self.assertTrue(known['mckay-AMERICA']['text'].endswith(
            'Like priceless treasures sinking in the sand.'))
        self.assertEqual(known['yeats-aedh-wishes-for-the-cloths-of-heaven']['line_count'], 8)
        self.assertTrue(known['yeats-aedh-wishes-for-the-cloths-of-heaven']['text'].endswith(
            'Tread softly because you tread on my dreams.'))
        flight = known['teasdale-rivers-id00023']
        self.assertEqual(flight['line_count'], 8)
        self.assertEqual(len(flight['text'].split('\n\n')), 2)
        self.assertTrue(flight['text'].endswith(
            'BUT WHAT IF I HEARD MY FIRST LOVE CALLING ME ONCE MORE?'))
        self.assertEqual(known['millay-april-link2H_4_0003']['line_count'], 12)
        self.assertTrue(known['millay-april-link2H_4_0003']['text'].endswith(
            'I know what sound is there.'))
        self.assertEqual(known['housman-last-link2H_4_0015']['line_count'], 8)
        self.assertEqual(known['housman-last-link2H_4_0002']['title'],
            'As I gird on for fighting')
        self.assertEqual(counts['lear']['complete_poems'], 112)
        self.assertEqual(counts['browning']['complete_poems'], 44)
        self.assertEqual(known['lear-rhyme1_1']['line_count'], 4)
        self.assertTrue(known['lear-rhyme1_1']['text'].endswith(
            'That remarkable Man with a nose.'))
        self.assertEqual(known['herrick-id_1.p83']['line_count'], 14)
        self.assertNotIn('[C]', known['herrick-id_1.p8']['text'])
        self.assertNotIn('[D]', known['herrick-id_1.p8']['text'])
        self.assertTrue(known['herrick-id_1.p83']['text'].endswith(
            'Is too precise in every part.'))
        self.assertEqual(known['rossetti-poems-remember']['line_count'], 14)
        self.assertTrue(known['rossetti-poems-remember']['text'].endswith(
            'Than that you should remember and be sad.'))
        self.assertEqual(known['browning-I']['line_count'], 14)
        self.assertEqual(known['masters-chapM16']['line_count'], 9)
        self.assertEqual(known['yeats-swans-an-irish-airman-foresees-his-death']['line_count'], 16)
        self.assertEqual(known['stevenson-underwoods-page1']['text'],
            'Go, little book, and wish to all\nFlowers in the garden, meat in the hall,\n'
            'A bin of wine, a spice of wit,\nA house with lawns enclosing it,\n'
            'A living river by the door,\nA nightingale in the sycamore!')
        self.assertEqual(known['stevenson-underwoods-page66']['title'], 'A CAMP')
        self.assertEqual(known['stevenson-underwoods-page67']['title'],
                         'THE COUNTRY OF THE CAMISARDS')
        self.assertEqual(known['teasdale-moon-Let_It_Be_You']['line_count'], 12)
        self.assertEqual(len(known['teasdale-moon-Let_It_Be_You']['text'].split('\n\n')), 3)
        self.assertEqual(known['millay-renascence-god-s-world']['line_count'], 14)

    def test_rebuild_bytes_and_binding(self):
        for suffix in ('.ttf', '.woff2', '.json'):
            self.assertEqual((ROOT/f'poem-oracle{suffix}').read_bytes(),
                             self.fresh.with_suffix(suffix).read_bytes(), suffix)
        self.assertEqual(hashlib.sha256((ROOT/'poem-oracle.ttf').read_bytes()).hexdigest(),
                         self.manifest['fontSha256'])
        self.assertEqual(hashlib.sha256((ROOT/'poems.json').read_bytes()).hexdigest(),
                         self.manifest['corpusSha256'])

    def test_font_coverage_outlines_and_attribution(self):
        for path in (ROOT/'poem-oracle.ttf', ROOT/'poem-oracle.woff2', self.fresh):
            with TTFont(path) as font:
                self.assertEqual(set(font.getBestCmap()), {ord(c) for c in CHARACTERS})
                self.assertEqual(font['OS/2'].fsType, 0)
                self.assertIn('Copyright 2015 Google Inc.', font['name'].getDebugName(0))
                self.assertIn('Michael Brackx', font['name'].getDebugName(0))
                self.assertIn('Apache License', font['name'].getDebugName(13))
                lookups = font['GSUB'].table.LookupList.Lookup
                self.assertTrue(any(l.LookupType == 7 and l.SubTable[0].ExtensionLookupType == 8
                                    for l in lookups))
                for panel in self.manifest['poems']:
                    self.assertEqual(font.getGlyphID(panel['glyph']), panel['glyphId'])
                    glyph = font['glyf'][panel['glyph']]
                    self.assertTrue(glyph.isComposite())
                    self.assertGreaterEqual(glyph.xMin, 0)
                    self.assertGreaterEqual(glyph.yMin, 0)
                    self.assertLessEqual(glyph.xMax, panel['width'])
                    self.assertLessEqual(glyph.yMax, panel['height'])

    @unittest.skipUnless(SHAPER, 'Install HarfBuzz for actual shaping tests')
    def test_all_poems_and_long_inputs_match_independent_hash(self):
        count = len(self.poems)
        reachable = all_poem_seeds(count)
        self.assertEqual(len(reachable), count)
        rng = random.Random(42)
        texts = list(reachable.values()) + ['hope', 'hope!', 'after the rain', 'café — déjà vu',
            'A paragraph. '*200, 'a'*MAX_INPUT, 'Z'*MAX_INPUT, ' hello  world ',
            normalize('cafe\u0301\r\na second line\tand a tab')]
        texts += [''.join(rng.choice(CHARACTERS) for _ in range(rng.randrange(1, 256)))
                  for _ in range(70)]
        texts = [normalize(text) for text in texts]
        for path in (ROOT/'poem-oracle.ttf', self.fresh):
            result = subprocess.run([SHAPER, str(path), '--direction=ltr', '--script=latn',
                '--language=en', '--text-file=-', '--output-format=json'],
                input='\n'.join(texts)+'\n', text=True, capture_output=True, check=True, timeout=60)
            outputs = [json.loads(row) for row in result.stdout.splitlines()]
            self.assertEqual(len(outputs), len(texts))
            for text, glyphs in zip(texts, outputs):
                index = select_index(text, count)
                self.assertEqual([g['g'] for g in glyphs if g['g'] != 'ghost'],
                                 [f'poem_{index:04d}'], text)
                self.assertEqual(sum(g['ax'] for g in glyphs), self.manifest['poems'][index]['width'])

    @unittest.skipUnless(SHAPER, 'Install HarfBuzz for actual shaping tests')
    def test_disabling_feature_removes_poem_computation(self):
        result = subprocess.run([SHAPER, str(ROOT/'poem-oracle.ttf'), 'hope',
            '--features=rlig=0', '--output-format=json'], text=True, capture_output=True, check=True)
        self.assertFalse(any(g['g'].startswith('poem_') for g in json.loads(result.stdout)))


if __name__ == '__main__':
    unittest.main()
