# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Typography checks for the previously published game fonts."""
from pathlib import Path
import unittest

from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont
from game_text import centered_lettering, lettering, text_width

GAMES = ('hexapawn', 'tic-tac-toe', 'nim', 'mu-torere', 'cram', 'wythoff',
         'notakto', 'backgammon', 'text-adventure', 'connect-four')
TEXT_GLYPHS = {'text-adventure': 'line_0', 'backgammon': 'status_complete'}


class TypographyTests(unittest.TestCase):
    def test_published_fonts_retain_attribution_and_smooth_text(self):
        for game in GAMES:
            path = Path(__file__).resolve().parents[1]/game/(game+'-font.ttf')
            with self.subTest(game=game), TTFont(path) as font:
                self.assertIn('Copyright 2015 Google Inc.', font['name'].getDebugName(0))
                self.assertIn('Michael Brackx', font['name'].getDebugName(0))
                self.assertIn('Roboto', font['name'].getDebugName(7))
                license_text = font['name'].getDebugName(13)
                self.assertIn('GPL-3.0' if game == 'connect-four' else 'Apache License', license_text)
                name = TEXT_GLYPHS.get(game, 'status_ready')
                glyph = font['glyf'][name]
                _, _, flags = glyph.getCoordinates(font['glyf'])
                self.assertTrue(any(not flag & 1 for flag in flags), name)

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


if __name__ == '__main__':
    unittest.main()
