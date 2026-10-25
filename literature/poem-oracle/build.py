# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Build a self-contained poem-selection font with FontTools and Brotli."""

import argparse
from functools import cache
import hashlib
import json
import sys
from pathlib import Path

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import GlyphComponent
from fontTools.ttLib.tables.otBase import USE_HARFBUZZ_REPACKER

from model import CHARACTERS, MAX_INPUT, MULTIPLIER, SEEDS

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1]))
from fontbuild import compact_glyphs, compact_woff2
SOURCE = ROOT.parents[1]/'decoders/shared/fonts/roboto-2'
PADDING, BODY_CAP, LINE_STEP = 240, 160, 260


def empty():
    return TTGlyphPen(None).glyph()


def build(output):
    poems = json.loads((ROOT/'poems.json').read_text())
    count = len(poems)
    if count <= len(CHARACTERS):
        raise ValueError('The state space must exceed the input alphabet.')
    glyphs, metrics, panels = {}, {}, []

    def add(name, glyph=None, width=0):
        glyphs[name] = empty() if glyph is None else glyph
        metrics[name] = (round(width), 0)
        return name

    # Shared scaled letters retain curves and support the source's punctuation.
    faces = {weight: TTFont(SOURCE/f'Roboto-{weight.title()}.ttf')
             for weight in ('regular', 'bold')}

    @cache
    def letter(char, weight, cap):
        face = faces[weight]
        name = face.getBestCmap().get(ord(char))
        if name is None:
            raise ValueError(f'Unsupported outline: {char!r}')
        scale = cap / face['OS/2'].sCapHeight
        recording = DecomposingRecordingPen(face.getGlyphSet())
        face.getGlyphSet()[name].draw(recording)
        pen = TTGlyphPen(None)
        recording.replay(TransformPen(pen, (scale, 0, 0, scale, 0, 0)))
        result = f'letter_{weight}_{cap}_{ord(char):04x}'
        advance = face['hmtx'][name][0] * scale
        add(result, pen.glyph(), advance)
        return result, advance

    def width(text, weight='regular', cap=BODY_CAP):
        return sum(letter(char, weight, cap)[1] for char in text)

    def draw(pen, text, y, weight='regular', cap=BODY_CAP):
        x = PADDING
        for char in text:
            name, advance = letter(char, weight, cap)
            if char != ' ':
                pen.addComponent(name, (1, 0, 0, 1, round(x), round(y)))
            x += advance

    # Ordinary input remains readable if rlig is disabled.
    add('.notdef')
    pen = TTGlyphPen(None)
    for pts in [[(70, 0), (70, 700), (600, 700), (600, 0)],
                [(120, 50), (550, 50), (550, 650), (120, 650)]]:
        pen.moveTo(pts[0])
        for point in pts[1:]:
            pen.lineTo(point)
        pen.closePath()
    glyphs['.notdef'] = pen.glyph()
    metrics['.notdef'] = (670, 70)
    add('ghost')
    cmap = {ord(c): letter(c, 'regular', 711)[0] for c in CHARACTERS}
    for i in range(count):
        add(f'hash_{i}')

    for index, poem in enumerate(poems):
        lines = poem['text'].splitlines()
        body_height = sum(LINE_STEP if line else LINE_STEP//2 for line in lines)
        height = body_height + 1060
        panel_width = round(max(4000, width(poem['title'], 'bold', 180),
                                width(poem['author'], cap=130),
                                *(width(line) for line in lines)) + 2*PADDING)
        if max(height, panel_width) > 30000:
            raise ValueError('Poem exceeds TrueType coordinate bounds: '+poem['id'])
        pen = TTGlyphPen(glyphs)
        draw(pen, poem['title'], height-330, 'bold', 180)
        y = height-850
        for line in lines:
            if line:
                draw(pen, line, y)
            y -= LINE_STEP if line else LINE_STEP//2
        draw(pen, poem['author'], 130, cap=130)
        name = add(f'poem_{index:04d}', pen.glyph(), panel_width)
        panels.append(dict(glyph=name, index=index, width=panel_width, height=height))

    # Every attribution occupies the same position. Store each author's exact
    # component sequence once, after existing glyphs so their IDs stay stable.
    original_order = list(glyphs)
    original_glyphs = dict(glyphs)
    original_components = {name: glyph.components for name, glyph in glyphs.items()
                           if glyph.isComposite()}
    authors = {}
    for poem, panel in zip(poems, panels):
        author = poem['author']
        if author not in authors:
            pen = TTGlyphPen(glyphs)
            draw(pen, author, 130, cap=130)
            authors[author] = add(f'author_{len(authors)}', pen.glyph())
        part = GlyphComponent()
        part.glyphName, part.x, part.y, part.flags = authors[author], 0, 0, 4
        glyph = glyphs[panel['glyph']]
        author_letters = sum(char != ' ' for char in author)
        glyph.components = [*glyph.components[:-author_letters], part]

    order = list(glyphs)
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder(order)
    builder.setupCharacterMap(cmap)
    builder.setupGlyf(glyphs)
    for name, glyph in glyphs.items():
        if glyph.numberOfContours:
            glyph.recalcBounds(builder.font['glyf'])
            metrics[name] = (metrics[name][0], glyph.xMin)
    builder.setupHorizontalMetrics(metrics)
    top = max(panel['height'] for panel in panels)
    builder.setupHorizontalHeader(ascent=top, descent=-220)
    builder.setupNameTable(dict(familyName='Poem Oracle', styleName='Regular',
        uniqueFontIdentifier='PoemOracle-1.0', fullName='Poem Oracle',
        psName='PoemOracle-Regular', version='Version 1.0',
        copyright='Copyright 2015 Google Inc. All Rights Reserved.\nCopyright 2026 Michael Brackx',
        trademark='Roboto is a trademark of Google.',
        description='Poem selection and composition by Michael Brackx. Modified Roboto 2 '
                    'Regular and Bold outlines (v2.138). Historical poem texts are public domain; '
                    'edition provenance accompanies the font in sources.json.',
        licenseDescription='Licensed under the Apache License, Version 2.0. '
                           'Historical poem texts are public domain.',
        licenseInfoURL='https://www.apache.org/licenses/LICENSE-2.0'))
    builder.setupOS2(sTypoAscender=top, sTypoDescender=-220, usWinAscent=top,
                    usWinDescent=220, fsType=0)
    builder.setupPost()
    builder.setupMaxp()

    states = [f'hash_{i}' for i in range(count)]
    outputs = [f'poem_{i:04d}' for i in range(count)]
    inputs = [cmap[ord(char)] for char in CHARACTERS]
    seeds = [f'hash_{SEEDS[char]}' for char in CHARACTERS]
    fea = ['languagesystem DFLT dflt;', 'languagesystem latn dflt;',
           '@STATE = ['+' '.join(states)+'];',
           '@POEM = ['+' '.join(outputs)+'];',
           '@GUARD = [@STATE @POEM];',
           '@SEED = ['+' '.join(seeds)+'];',
           'lookup INIT { sub ['+' '.join(inputs)+'] by @SEED; } INIT;',
           'lookup HASH useExtension {']
    # A single reverse chaining lookup scans the run right to left. Only the
    # original character seed at each position is the target; its right-hand
    # neighbor has already become the hash of the whole suffix.
    for suffix in range(count):
        targets = ' '.join(f'hash_{(SEEDS[c]+MULTIPLIER*suffix)%count}' for c in CHARACTERS)
        fea.append(f'rsub @SEED\' hash_{suffix} by [{targets}];')
    fea += ['} HASH;',
            'lookup OUTPUT { sub @STATE by @POEM; } OUTPUT;',
            'lookup FIRST { ignore sub @GUARD @STATE\';',
            'sub @STATE\' lookup OUTPUT; } FIRST;',
            'lookup HIDE { sub @STATE by ghost; } HIDE;',
            'feature rlig { lookup INIT; lookup HASH; lookup FIRST; lookup HIDE; } rlig;']
    addOpenTypeFeaturesFromString(builder.font, '\n'.join(fea))
    builder.font['head'].created = builder.font['head'].modified = 3875644800
    builder.font.recalcTimestamp = False
    output.parent.mkdir(parents=True, exist_ok=True)
    compact_glyphs(builder.font, positioned=True)
    builder.font.save(output)
    font_bytes = output.read_bytes()
    # WOFF2 compresses the original flat letter sequences more effectively.
    # Restore every original outline and omit all private TTF sharing helpers.
    for name, parts in original_components.items():
        original_glyphs[name].components = parts
    builder.font['glyf'].glyphs = original_glyphs
    builder.font['hmtx'].metrics = {name: builder.font['hmtx'].metrics[name]
                                  for name in original_order}
    builder.font.setGlyphOrder(original_order)
    builder.font['glyf'].setGlyphOrder(original_order)
    builder.font['post'].extraNames = [name for name in builder.font['post'].extraNames
                                      if name in original_glyphs]
    builder.font.cfg[USE_HARFBUZZ_REPACKER] = False
    builder.font.flavor = 'woff2'
    builder.font.save(output.with_suffix('.woff2'))
    compact_woff2(output.with_suffix('.woff2'))
    manifest = dict(version=1, count=count, multiplier=MULTIPLIER, maxInput=MAX_INPUT,
                    alphabet=CHARACTERS, bodyCap=BODY_CAP, padding=PADDING,
                    fontSha256=hashlib.sha256(font_bytes).hexdigest(),
                    corpusSha256=hashlib.sha256((ROOT/'poems.json').read_bytes()).hexdigest(),
                    poems=[dict(**panel, glyphId=builder.font.getGlyphID(panel['glyph']),
                                poemId=poem['id']) for panel, poem in zip(panels, poems)])
    output.with_suffix('.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    for face in faces.values():
        face.close()
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'poem-oracle.ttf')
    args = parser.parse_args()
    result = build(args.output)
    print(f'Built {result["count"]} poems into {args.output} and WOFF2.')
