# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Original base-font, published typography, and embedded-document checks."""
from pathlib import Path
import tempfile
import unittest
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont
from game_sans import CHARACTERS, FONT_DIR, build_font, face
from game_text import centered_lettering, lettering, text_width

GAMES = ('hexapawn', 'tic-tac-toe', 'nim', 'mu-torere', 'cram', 'wythoff',
         'notakto', 'backgammon', 'text-adventure', 'connect-four', 'gardner',
         'achi', 'chomp', 'dodgem', 'domineering', 'dots-and-boxes', 'kayles')
TEXT_GLYPHS = {'text-adventure': 'line_0', 'backgammon': 'status_complete'}
TEXT_GLYPHS['gardner'] = 'board'


class TypographyTests(unittest.TestCase):
    def test_published_fonts_use_original_smooth_text(self):
        for game in GAMES:
            path = Path(__file__).resolve().parents[1]/game/(game+'-font.ttf')
            with self.subTest(game=game), TTFont(path) as font:
                self.assertIn('Michael Brackx', font['name'].getDebugName(0))
                names = '\n'.join(record.toUnicode() for record in font['name'].names)
                self.assertIn('Game Sans', names)
                self.assertNotIn('Google', names)
                self.assertNotIn('Roboto', names)
                license_text = font['name'].getDebugName(13)
                self.assertIn('Apache License', license_text)
                name = TEXT_GLYPHS.get(game, 'status_ready')
                glyph = font['glyf'][name]
                _, _, flags = glyph.getCoordinates(font['glyf'])
                self.assertTrue(any(not flag & 1 for flag in flags), name)

    def test_base_fonts_rebuild_exactly_and_cover_the_small_alphabet(self):
        self.assertEqual(len(CHARACTERS), 76)
        for weight in ('regular', 'bold'):
            bundled = FONT_DIR/f'GameSans-{weight.title()}.ttf'
            with tempfile.TemporaryDirectory() as temp:
                rebuilt = Path(temp)/'base.ttf'
                build_font(rebuilt, weight)
                self.assertEqual(rebuilt.read_bytes(), bundled.read_bytes())
            with TTFont(bundled) as font:
                self.assertEqual(set(font.getBestCmap()), set(map(ord, CHARACTERS)))
                self.assertEqual(font['OS/2'].fsType, 0)
                self.assertEqual(font['OS/2'].usWeightClass, 700 if weight == 'bold' else 400)
                for char, name in font.getBestCmap().items():
                    self.assertEqual(font['glyf'][name].numberOfContours == 0, char == ord(' '))
        _, regular = face('regular')
        _, bold = face('bold')
        self.assertEqual({c: g[1] for c, g in regular.items()}, {c: g[1] for c, g in bold.items()})
        # These characters encode moves and counts; none may be ambiguous copies.
        self.assertEqual(len({repr(bold[c][0]) for c in '0O1Il'}), 5)

    def test_game_documents_embed_current_original_fonts(self):
        root = Path(__file__).resolve().parents[1]
        for game in ('snake-fixed', 'snake-dynamic', 'text-adventure'):
            with self.subTest(game=game), ZipFile(root/game/(game+'.odt')) as document:
                self.assertEqual(document.read('Fonts/GameSans-Regular.ttf'),
                                 (FONT_DIR/'GameSans-Regular.ttf').read_bytes())
                self.assertEqual(document.read('Fonts/computational.ttf'),
                                 (root/game/(game+'-font.ttf')).read_bytes())
                self.assertNotIn('Fonts/Roboto-Regular.ttf', document.namelist())
                body = ET.fromstring(document.read('content.xml'))
                text = ''.join(body.itertext())
                self.assertFalse(set(text)-set(CHARACTERS)-set('\n\t\r'))
                for xml in ('content.xml', 'styles.xml', 'META-INF/manifest.xml'):
                    self.assertIn(b'Fonts/GameSans-Regular.ttf', document.read(xml))
                    self.assertNotIn(b'Roboto', document.read(xml))

    def test_proportional_spacing_and_accented_labels(self):
        self.assertLess(text_width('iiii'), text_width('WWWW'))
        for text in ('Mū tōrere', 'Misère Nim', 'First 2    Second 2'):
            pen = BoundsPen(None)
            centered_lettering(pen, text, 900, 100, 10)
            self.assertIsNotNone(pen.bounds)
            self.assertAlmostEqual((pen.bounds[0]+pen.bounds[2])/2, 900)

    def test_left_alignment_and_blank_labels(self):
        pen = BoundsPen(None)
        lettering(pen, 'Your turn', 100, 100)
        self.assertGreaterEqual(pen.bounds[0], 100)
        empty = BoundsPen(None)
        centered_lettering(empty, '   ', 900, 100)
        self.assertIsNone(empty.bounds)

    def test_missing_characters_and_weights_fail_explicitly(self):
        with self.assertRaisesRegex(ValueError, 'Unsupported label character'):
            text_width('🙂')
        with self.assertRaisesRegex(ValueError, 'Unknown text weight'):
            text_width('Hello', weight='italic')


if __name__ == '__main__':
    unittest.main()
