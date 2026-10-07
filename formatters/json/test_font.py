# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Independent lexical and spacing checks for the JSON formatting font."""

import importlib.util
import json
from pathlib import Path
import random
import re
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile
from xml.etree import ElementTree as ET

from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SHAPER = shutil.which("hb-shape")
NEEDS_SHAPER = unittest.skipUnless(SHAPER, "Install HarfBuzz's hb-shape for shaping checks")
spec = importlib.util.spec_from_file_location("json_builder", HERE / "build.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")
STRING = re.compile(r'"(?:\\.|[^"\\])*"')
PUNCTUATION = "{}[]:,"
BOUNDARY = " " + PUNCTUATION
ROLES = ("key", "string", "number", "literal", "punct")


def reference(text):
    """A regex lexer, independent of the font's forward/backward state rules."""
    output = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == '"':
            match = STRING.match(text, index)
            end = match.end() if match else len(text)
            following = text[end:].lstrip(" ")
            role = "key" if match and following.startswith(":") else "string"
            output.extend((value, role) for value in text[index:end])
        elif char == " ":
            end = index + 1
            while end < len(text) and text[end] == " ":
                end += 1
            previous = text[index - 1] if index else ""
            following = text[end] if end < len(text) else ""
            if not (previous and previous in "{[:,") and not (following and following in PUNCTUATION):
                output.append((" ", "plain"))
        elif char in PUNCTUATION:
            end = index + 1
            output.append((char, "punct"))
            if char in ":,":
                output.append((" ", "punct"))
        else:
            end = index + 1
            while end < len(text) and text[end] not in BOUNDARY + '"':
                end += 1
            word = text[index:end]
            left = index == 0 or text[index - 1] in BOUNDARY
            right = end == len(text) or text[end] in BOUNDARY
            role = ("number" if left and right and NUMBER.fullmatch(word) else
                    "literal" if left and right and word in ("true", "false", "null") else "plain")
            output.extend((value, role) for value in word)
        index = end
    return output


def outlines(font, name):
    pen = DecomposingRecordingPen(font.getGlyphSet())
    font.getGlyphSet()[name].draw(pen)
    return pen.value


class JSONFontTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.fresh = Path(cls.tmp.name) / "fresh.ttf"
        builder.build_font(cls.fresh)
        cls.paths = (HERE / "json-font.ttf", cls.fresh)
        cls.fonts = [TTFont(path) for path in cls.paths]
        cls.source = TTFont(builder.DEFAULT_BASE)

    @classmethod
    def tearDownClass(cls):
        for font in [*cls.fonts, cls.source]:
            font.close()
        cls.tmp.cleanup()

    def display(self, font, rows):
        # Read source components and actual COLR palette indices rather than
        # trusting a generated glyph's semantic name to describe its output.
        inverse = {name: chr(code) for code, name in self.source.getBestCmap().items()}
        visible = []
        for row in rows:
            name = row["g"]
            self.assertFalse(name.startswith("json.cand."), "Unreleased number candidate")
            glyph = font["glyf"][name]
            self.assertEqual(row["ax"], font["hmtx"][name][0])
            if name == "json.gap":
                self.assertEqual(row["ax"], 0)
                self.assertEqual(glyph.numberOfContours, 0)
                continue
            self.assertTrue(glyph.isComposite(), name)
            role = "plain"
            if name in font["COLR"].ColorLayers:
                layer = font["COLR"].ColorLayers[name]
                self.assertEqual(len(layer), 1)
                role = ROLES[layer[0].colorID]
                self.assertEqual(outlines(font, name), outlines(font, layer[0].name))
            advance = 0
            chars = ""
            for component in glyph.components:
                original, transform = component.getComponentInfo()
                self.assertEqual(transform, (1, 0, 0, 1, advance, 0))
                self.assertIn(original, inverse)
                chars += inverse[original]
                advance += self.source["hmtx"][original][0]
            visible.extend((char, role) for char in chars)
            if chars in (":", ",") and role == "punct":
                self.assertEqual(row["ax"] - advance, self.source["hmtx"][self.source.getBestCmap()[32]][0])
                visible.append((" ", "punct"))
            else:
                self.assertEqual(row["ax"], advance)
        return visible

    def check_text(self, text, expected=None):
        expected = reference(text) if expected is None else expected
        for path, font in zip(self.paths, self.fonts):
            with self.subTest(font=path.name, text=text[:90]):
                output = subprocess.check_output([
                    SHAPER, str(path), "--text=" + text, "--output-format=json", "--direction=ltr",
                    "--script=latn", "--features=kern=0"], text=True, timeout=15)
                # hb-shape emits no record for empty input.
                rows = json.loads(output) if output.strip() else []
                self.assertEqual(self.display(font, rows), expected)

    @NEEDS_SHAPER
    def test_basic_spacing_and_roles(self):
        source = '{  "name" : "Ada  Lovelace" , "count":3,"active":true,"note":null }'
        expected = reference(source)
        self.assertEqual("".join(char for char, _ in expected),
                         '{"name": "Ada  Lovelace", "count": 3, "active": true, "note": null}')
        self.check_text(source, expected)
        for text in ('{}', '[]', ' {  } ', '[  1   , 2   ]', '"value"', '0', 'false', 'null', ''):
            self.check_text(text)

    @NEEDS_SHAPER
    def test_strings_escape_parity_and_keys(self):
        values = {'quote': 'say "hi"', 'path': 'C:\\tmp\\', 'empty': '',
                  'literal': '{ [ : , ] } true false null 012  3'}
        self.check_text(json.dumps(values))
        for count in range(1, 9):
            self.check_text(json.dumps({'\\' * count + '"': '\\' * count + '" after  ,  :  '}))
        self.check_text(r'{"\u0061": "\u03b1", "slash": "\/", "line": "\n"}')
        self.check_text('{""   :   "", "a:b,c": "  leading and trailing  "}')
        self.check_text('"value" : 0')

    @NEEDS_SHAPER
    def test_unicode_glyphs_in_forced_single_run(self):
        # This low-level test forces Latin shaping; browsers may split scripts.
        self.check_text(json.dumps({'café': 'Été,  αβ: Привет', 'n': 7}, ensure_ascii=False))

    @NEEDS_SHAPER
    def test_numbers_and_keyword_boundaries(self):
        for value in ('0', '-0', '1', '-1', '1234567890', '0.0', '-0.5', '1E9', '0e0',
                      '1E+09', '-123.456e-789', 'true', 'false', 'null'):
            for text in (value, '[' + value + ']', '{"v":  ' + value + '  }'):
                self.check_text(text)
        for value in ('00', '01', '-01', '+1', '.5', '-.5', '1.', '1e', '1e+', '1E-',
                      '1.2.3', '--1', 'NaN', 'Infinity', 'truefalse', 'xtrue', 'truex',
                      'False', 'null0', '0null', '1e2x'):
            self.check_text('[' + value + ']')
        for text in ('1  2', 'true  false', 'true"x"', '"x"null', 'null:null'):
            self.check_text(text)

    @NEEDS_SHAPER
    def test_incomplete_text_stays_visible(self):
        for text in ('{', '{"', '{"open  :  , true', '{"a":', '{"a": -', '{"a": 1e+',
                     '"ends with \\', '"invalid \\q escape"', '[[1,2}', 'foo bar'):
            self.check_text(text)

    @NEEDS_SHAPER
    def test_long_and_nested_values(self):
        self.check_text(json.dumps({'long': ('ab  , : \\" ' * 150) + 'end', 'n': 7}))
        self.check_text('[' * 100 + '1' + ']' * 100)
        self.check_text('1' * 1200 + 'e-10')

    @NEEDS_SHAPER
    def test_varied_documents_and_malformed_tokens(self):
        rng = random.Random(507)
        for _ in range(35):
            value = {'a': rng.randint(-10000, 10000), 'b': [True, None, rng.random()],
                     'text': ''.join(rng.choices('abc : , {} [] \\"', k=40))}
            # Generate valid JSON with deliberately excessive outside spacing.
            text = json.dumps(value, separators=('   ,   ', '  :    '))
            self.check_text(text)
        for _ in range(70):
            token = ''.join(rng.choices('0123456789eE+-.truefalsnXYZ', k=rng.randrange(1, 30)))
            self.check_text('[' + token + ']')

    def test_palette_outlines_and_attribution(self):
        for font in self.fonts:
            self.assertEqual(font["name"].getBestFamilyName(), "JSON Formatter")
            self.assertNotIn("GPOS", font)
            palette = font["CPAL"].palettes[0]
            self.assertEqual(len(palette), 5)
            for actual, expected in zip(palette, builder.PALETTE):
                self.assertEqual((actual.red, actual.green, actual.blue, actual.alpha),
                                 (*[int(expected[index:index + 2], 16) for index in (1, 3, 5)], 255))
            for char in 'aAzZ0"\\éαП':
                original = self.source.getBestCmap()[ord(char)]
                for prefix in ('outside', 'key', 'string'):
                    name = 'json.' + prefix + '.' + original
                    self.assertEqual(outlines(font, name), outlines(self.source, original))
                    self.assertEqual(font['hmtx'][name], self.source['hmtx'][original])
            for name_id in (0, 7, 13, 14):
                self.assertIn(self.source['name'].getDebugName(name_id), font['name'].getDebugName(name_id))
            self.assertIn('Formatter modifications', font['name'].getDebugName(0))
            self.assertIn('json formatter', font['name'].getDebugName(10))

    def test_color_changes_font_identity(self):
        palette = builder.PALETTE
        try:
            builder.PALETTE = ('#000000', *palette[1:])
            output = Path(self.tmp.name) / 'recolored.ttf'
            builder.build_font(output)
            with TTFont(output) as recolored:
                self.assertNotEqual(recolored['name'].getDebugName(6), self.fonts[1]['name'].getDebugName(6))
        finally:
            builder.PALETTE = palette

    def test_output_safety_import_and_custom_name(self):
        original = self.paths[0].read_bytes()
        with self.assertRaisesRegex(ValueError, 'Output must differ'):
            builder.build_font(builder.DEFAULT_BASE)
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, '-c',
                                     'import runpy; runpy.run_path(' + repr(str(HERE / 'build.py')) + ')'],
                                    cwd=directory, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(list(Path(directory).iterdir()), [])
            result = subprocess.run([sys.executable, str(HERE / 'build.py'), '--output', 'custom.ttf',
                                     '--name', 'Custom JSON'], cwd=directory, capture_output=True,
                                    text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            with TTFont(Path(directory) / 'custom.ttf') as font:
                self.assertEqual(font['name'].getBestFamilyName(), 'Custom JSON')
        self.assertEqual(self.paths[0].read_bytes(), original)

    def test_specimen_embeds_current_font(self):
        with ZipFile(HERE / 'json.odt') as odt:
            self.assertEqual(odt.read('Fonts/computational.ttf'), self.paths[0].read_bytes())
            self.assertEqual(odt.read('Fonts/Roboto-Regular.ttf'), builder.DEFAULT_BASE.read_bytes())
            self.assertEqual(odt.read('THIRD_PARTY_NOTICES.txt'), (ROOT / 'THIRD_PARTY_NOTICES.md').read_bytes())
            document = ET.fromstring(odt.read('content.xml'))
        specimens = runpy.run_path(str(ROOT / 'specimens/build.py'))
        spec = next(item for item in specimens['SPECS'] if item.folder == 'formatters/json')
        ns = specimens['NS']
        paragraphs = document.findall('.//text:p', ns)
        for style in ('Source', 'Rendered'):
            values = []
            for paragraph in paragraphs:
                if paragraph.get(f"{{{ns['text']}}}style-name") != style:
                    continue
                # Ordinary XML spaces collapse in ODF; text:s preserves counts.
                value = re.sub(r' +', ' ', paragraph.text or '')
                for child in paragraph:
                    self.assertEqual(child.tag, f"{{{ns['text']}}}s")
                    value += ' ' * int(child.get(f"{{{ns['text']}}}c", '1'))
                    value += re.sub(r' +', ' ', child.tail or '')
                values.append(value)
            self.assertEqual(values, [example.source for example in spec.examples])


if __name__ == '__main__':
    unittest.main()
