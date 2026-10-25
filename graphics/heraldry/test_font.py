# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Exercise the distributed font through real HarfBuzz, including every composition."""

import itertools
from pathlib import Path
import tempfile
import unittest

from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
import pathops
import uharfbuzz as hb

from build import build_font, DEFAULT_BASE

HERE = Path(__file__).resolve().parent
# Keep the conformance vocabulary independent from the builder's production lists.
COLORS = ('or', 'argent', 'azure', 'gules', 'sable', 'vert', 'purpure')
DIVISIONS = ('per pale', 'per fess', 'per bend', 'per bend sinister',
             'per chevron', 'per saltire', 'quarterly')
ORDINARIES = ('chief', 'fess', 'pale', 'bend', 'bend sinister', 'chevron',
              'cross', 'saltire', 'bordure')
CHARGES = (('mullet', 'mullets'), ('lozenge', 'lozenges'), ('crescent', 'crescents'),
           ('heart', 'hearts'), ('fleur-de-lis', 'fleurs-de-lis'),
           ('lion rampant', 'lions rampant'))


class HeraldryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = HERE / 'heraldry-font.ttf'
        cls.font = TTFont(cls.path)
        cls.addClassCleanup(cls.font.close)
        cls.shaper = hb.Font(hb.Face(cls.path.read_bytes()))
        cls.upem = cls.font['head'].unitsPerEm
        cls.glyphs = cls.font.getGlyphSet()

    def shape(self, text, *, enabled=True, shaper=None):
        buffer = hb.Buffer()
        buffer.add_str(text)
        buffer.guess_segment_properties()
        hb.shape(shaper or self.shaper, buffer, {'liga': enabled, 'kern': False})
        names = [self.font.getGlyphName(item.codepoint) for item in buffer.glyph_infos]
        return names, buffer.glyph_positions

    def assert_shield(self, text, expected):
        names, positions = self.shape(text)
        self.assertEqual(names, [*expected, 'shield_end'], text)
        self.assertEqual([p.x_advance for p in positions], [0]*len(expected)+[self.upem], text)
        self.assertTrue(all((p.x_offset, p.y_offset, p.y_advance) == (0, 0, 0)
                            for p in positions), text)

    def outlines(self, text, enabled):
        names, positions = self.shape(text, enabled=enabled)
        pen = DecomposingRecordingPen(self.glyphs)
        x = 0
        for name, pos in zip(names, positions):
            self.glyphs[name].draw(TransformPen(pen, (1, 0, 0, 1, x+pos.x_offset, pos.y_offset)))
            x += pos.x_advance
        return pen.value, x

    def test_all_51800_compositions(self):
        fields = [(color, 'field_'+color) for color in COLORS]
        for division, first, second in itertools.product(DIVISIONS, COLORS, COLORS):
            fields.append((f'{division} {first} and {second}',
                           f'field_{division.replace(" ", "_")}_{first}_{second}'))
        devices = [('', None)]
        for name, color in itertools.product((*ORDINARIES, *(s for s, _ in CHARGES)), COLORS):
            devices.append((f', a {name} {color}',
                            f'device_{name.replace(" ", "_").replace("-", "_")}_1_{color}'))
        for (single, plural), color in itertools.product(CHARGES, COLORS):
            devices.append((f', three {plural} {color}',
                            f'device_{single.replace(" ", "_").replace("-", "_")}_3_{color}'))
        checked = 0
        for (field, field_name), (device, device_name) in itertools.product(fields, devices):
            expected = [field_name]+([device_name] if device_name else [])
            self.assert_shield('['+field+device+']', expected)
            checked += 1
        self.assertEqual(checked, 51800)

    def test_cases_spacing_and_optional_comma(self):
        for division in DIVISIONS:
            source = f'[{division} argent and azure, three fleurs-de-lis or]'
            expected = [f'field_{division.replace(" ", "_")}_argent_azure',
                        'device_fleur_de_lis_3_or']
            for case in (str.lower, str.upper, lambda s:' '.join(w.capitalize() for w in s.split(' '))):
                text = case(source)
                for gap in (' ', '  ', '   ', '\u00a0'):
                    self.assert_shield(text.replace(' ', gap), expected)
                self.assert_shield(text.replace(', ', ','), expected)
                self.assert_shield(text.replace(', ', ' '), expected)
        self.assert_shield('[Per PALE Argent AND azure, a Fleur-de-lis OR]',
                           ['field_per_pale_argent_azure', 'device_fleur_de_lis_1_or'])

    def test_invalid_input_preserves_exact_outlines_and_advance(self):
        sources = ('Azure, a chevron Or', '[Azure', 'Azure]', '[azure, a chevron or',
                   '[Azure, a dragon Or]', '[Per pale Azure]', '[Per pale Azure or Argent]',
                   '[azure, three chevrons or]', '[azure, two mullets or]',
                   '[azure, a mullets or]', '[azure, a mullet]', '[azure, a mullet or extra]',
                   '[azure, a mullet or, a heart argent]', '[azure a mullet or junk]',
                   '[azureish]', '[ultramarine]', '[azure,an or]', '[Azurea chevron Or]',
                   '[azure, a lion or]', '[azure, a lion passant or]', '[aZuRe]',
                   '[per pale azure and argent, a rose proper]', '[azure, a mullet or?]',
                   'The Azure sky and a pale Or moon.', '[azure    a chevron or]',
                   '[azure,\na chevron or]', '[ azure ]', '[azuré]', '[azure_]',
                   '[xazure]', '[azure1]', '[azureé]', '[fleur-de-lis-like]')
        for text in sources:
            with self.subTest(text=text):
                names, _ = self.shape(text)
                self.assertFalse(any(n.startswith(('field_', 'device_', 'valid_', 'tok_')) or
                                     n == 'shield_end' for n in names), names)
                self.assertEqual(self.outlines(text, True), self.outlines(text, False))

    def test_multiple_shields_and_surrounding_text(self):
        text = 'Gold: [Or]. [Gules, a heart Argent] / [Azure, three mullets Or]'
        names, _ = self.shape(text)
        self.assertEqual([n for n in names if n.startswith('field_')],
                         ['field_or', 'field_gules', 'field_azure'])
        self.assertEqual(names.count('shield_end'), 3)
        names, _ = self.shape(text, enabled=False)
        self.assertFalse(any(n.startswith(('field_', 'device_', 'lex_')) for n in names))

    def test_color_layers_geometry_and_font_notices(self):
        self.assertEqual(self.font['COLR'].version, 0)
        self.assertEqual(len(self.font['CPAL'].palettes[0]), 7)
        layers = self.font['COLR'].ColorLayers
        self.assertEqual(len(layers), 498)
        color_ids = {color: i for i, color in enumerate(COLORS)}
        for color in COLORS:
            self.assertEqual(layers['field_'+color][0].colorID, color_ids[color])
        for name, values in layers.items():
            if name.startswith('device_'):
                self.assertEqual(values[0].colorID, color_ids[name.rsplit('_', 1)[1]])
                self.assertTrue(self.font['glyf'][name].getCoordinates(self.font['glyf'])[1])
            for layer in values:
                glyph = self.font['glyf'][layer.name]
                self.assertTrue(glyph.getCoordinates(self.font['glyf'])[1])
                # Clipping keeps the devices within the shield; rim adds 7 units.
                self.assertGreaterEqual(glyph.xMin, round(.09*self.upem))
                self.assertLessEqual(glyph.xMax, round(.91*self.upem))
                self.assertGreaterEqual(glyph.yMin, 0)
                self.assertLessEqual(glyph.yMax, self.upem)
        self.assertEqual(self.font['OS/2'].fsType, 0)
        self.assertEqual(self.font['name'].getDebugName(1), 'Heraldry')
        copyright_text = self.font['name'].getDebugName(0)
        self.assertIn('Google', copyright_text)
        self.assertIn('Michael Brackx', copyright_text)
        self.assertIn('Apache', self.font['name'].getDebugName(13))

    def test_divisions_have_correct_tincture_orientation(self):
        # Samples are in heraldic geometry coordinates, independent of the builder.
        probes = {
            'per pale': ([(250, 750)], [(750, 750)]),
            'per fess': ([(500, 800)], [(500, 300)]),
            'per bend': ([(700, 800)], [(250, 600)]),
            'per bend sinister': ([(250, 750)], [(750, 600)]),
            'per chevron': ([(500, 850)], [(500, 400)]),
            'per saltire': ([(500, 800), (500, 200)], [(250, 500), (750, 500)]),
            'quarterly': ([(250, 750), (650, 300)], [(750, 750), (350, 300)]),
        }
        for division, (first, second) in probes.items():
            field = 'field_'+division.replace(' ', '_')+'_argent_azure'
            layer = self.font['COLR'].ColorLayers[field][1]
            path = pathops.Path()
            self.glyphs[layer.name].draw(path.getPen())
            for points, expected in ((first, False), (second, True)):
                for x, y in points:
                    with self.subTest(division=division, point=(x, y)):
                        self.assertEqual(path.contains((x*self.upem/1000, y*self.upem/1000)), expected)

    def test_reproducible_build_and_webfont_equivalence(self):
        with tempfile.TemporaryDirectory(prefix='heraldry-test-') as temporary:
            rebuilt = Path(temporary) / 'nested' / 'heraldry-font.ttf'
            build_font(rebuilt)
            for extension in ('.ttf', '.woff2', '.fea', '.json'):
                self.assertEqual(rebuilt.with_suffix(extension).read_bytes(),
                                 self.path.with_suffix(extension).read_bytes(), extension)
        with TTFont(self.path.with_suffix('.woff2')) as web:
            for tag in ('GSUB', 'glyf', 'hmtx', 'COLR', 'CPAL'):
                self.assertEqual(web[tag].compile(web), self.font[tag].compile(self.font), tag)

    def test_compressed_base_produces_real_ttf_without_modifying_source(self):
        with tempfile.TemporaryDirectory(prefix='heraldry-wrapper-') as temporary:
            directory = Path(temporary)
            base = directory / 'source.woff2'
            with TTFont(DEFAULT_BASE) as source:
                source.flavor = 'woff2'
                source.save(base)
            original = base.read_bytes()
            output = directory / 'result.ttf'
            build_font(output, base=base)
            self.assertEqual(output.read_bytes()[:4], b'\x00\x01\x00\x00')
            self.assertEqual(output.with_suffix('.woff2').read_bytes()[:4], b'wOF2')
            self.assertEqual(base.read_bytes(), original)

    def test_output_aliases_cannot_overwrite_base_or_other_outputs(self):
        with tempfile.TemporaryDirectory(prefix='heraldry-paths-') as temporary:
            directory = Path(temporary)
            base = directory / 'source.ttf'
            original = DEFAULT_BASE.read_bytes()
            base.write_bytes(original)
            # Font extensions do not establish file identity: same-stem sidecars
            # and both kinds of filesystem aliases must be protected up front.
            for ext in ('.woff2', '.fea', '.json'):
                sidecar_base = directory / ('same-stem'+ext)
                sidecar_base.write_bytes(original)
                output = sidecar_base.with_suffix('.ttf')
                with self.subTest(ext=ext), self.assertRaisesRegex(ValueError, 'differ'):
                    build_font(output, base=sidecar_base)
                self.assertEqual(sidecar_base.read_bytes(), original)
                self.assertFalse(output.exists())
            for kind in ('symlink', 'hardlink'):
                output = directory / (kind+'.ttf')
                sidecar = output.with_suffix('.woff2')
                if kind == 'symlink':
                    sidecar.symlink_to(base)
                else:
                    sidecar.hardlink_to(base)
                with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'differ'):
                    build_font(output, base=base)
                self.assertEqual(base.read_bytes(), original)
                self.assertFalse(output.exists())
            output = directory / 'mutual.ttf'
            output.write_bytes(b'Existing output')
            output.with_suffix('.woff2').symlink_to(output)
            with self.assertRaisesRegex(ValueError, 'differ'):
                build_font(output, base=base)
            self.assertEqual(output.read_bytes(), b'Existing output')


if __name__ == '__main__':
    unittest.main()
