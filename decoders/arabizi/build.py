#!/usr/bin/env python3
# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Build Arabizi Annotated, an OFL font with Arabic below intact Latin input.

FontTools builds outlines; hb-shape samples the pinned Noto Arabic joining forms.
No transliterator runs in the playground. Words are limited to 32 tokens.
"""
import argparse
import itertools
import json
from pathlib import Path
import subprocess

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.otlLib.builder import buildCoverage, buildLookup, buildSinglePos, buildValue
from fontTools.ttLib.tables import otTables
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.varLib.instancer import instantiateVariableFont

HERE = Path(__file__).resolve().parent
BASE = HERE / 'fonts/NotoNaskhArabic.ttf'
CELL = 600
ANNOTATION_SCALE = .34
MAX_TOKENS = 32
SINGLES = dict(zip('abtdrzsfgqklmnhwy', 'ابتدرزسفجقكلمنهوي'))
SINGLES.update({'e': 'ي', 'i': 'ي', 'o': 'و', 'u': 'و', 'j': 'ج', 'v': 'ڤ',
                'p': 'پ', 'c': 'ك', 'x': 'خ', '2': 'ء', '3': 'ع', '5': 'خ',
                '6': 'ط', '7': 'ح', '8': 'ق', '9': 'ص', "'": 'ء'})
SINGLES.update({key.upper(): value for key, value in list(SINGLES.items()) if key.isalpha()})
SINGLES.update({'S': 'ص', 'D': 'ض', 'T': 'ط', 'Z': 'ظ', 'H': 'ح'})
TOKENS = dict(SINGLES)
for spelling, arabic in {'sh': 'ش', 'kh': 'خ', 'gh': 'غ', 'th': 'ث', 'dh': 'ذ',
                         'ch': 'ش', 'aa': 'ا', 'ee': 'ي', 'ii': 'ي', 'oo': 'و',
                         'uu': 'و', "3'": 'غ', "7'": 'خ', "6'": 'ظ', "9'": 'ض'}.items():
    for variant in itertools.product(*[(c.lower(), c.upper()) if c.isalpha() else (c,) for c in spelling]):
        TOKENS[''.join(variant)] = arabic
# Letters that can connect to a following letter in logical (right-to-left) order.
DUAL = set('بتثجحخسشصضطظعغفقكلمنهيپڤ')
RIGHT = DUAL | set('اأإآدذرزوؤىة')
# Explicit whole-word spellings resolve common short vowels; this is not a lexicon.
WORDS = {'7abibi': 'حبيبي', 'habibi': 'حبيبي', 'salam': 'سلام', 'salaam': 'سلام',
         'shukran': 'شكرا', 'shokran': 'شكرا', 'mar7aba': 'مرحبا', 'mar7ba': 'مرحبا',
         '3arabi': 'عربي', 'keefak': 'كيفك', 'kifak': 'كيفك', 'ahlan': 'اهلا'}


def token_name(text):
    return 't' + ''.join(f'{ord(c):02x}' for c in text)


def annotation_advances(base):
    """Natural Latin advances rounded to even units for exact half-gap offsets."""
    cmap = base.getBestCmap()
    return {c: 2 * round(base['hmtx'][cmap[ord(c)]][0] * ANNOTATION_SCALE / 2)
            for c in SINGLES}


def sample_form(char, form):
    text = ('\u200d' if form in ('fina', 'medi') else '') + char + ('\u200d' if form in ('init', 'medi') else '')
    return json.loads(subprocess.check_output([
        'hb-shape', str(BASE), '--text=' + text, '--direction=rtl', '--script=arab',
        '--features=-rlig,-calt,-liga', '--remove-default-ignorables', '--output-format=json'], text=True))


def compact_annotations(font, source_widths):
    """Center a proportional source word, independently of the Arabic cells.

    Each preceding token contributes minus half its spare cell width, and each
    following token contributes plus half. Coverage-based contexts avoid the
    large overlapping-class matrices produced by a feature-source compiler.
    """
    glyph_map = font.getReverseGlyphMap()
    top_names = [token_name(s) + '.top' for s in source_widths]
    top_coverage = buildCoverage(top_names, glyph_map)
    arabic_names = {token_name(s) + '.' + form for s in source_widths
                    for form in ('isol', 'init', 'medi', 'fina')}
    # Treat the Arabic output as the ligature track so compaction can skip it.
    # Source glyphs and word boundaries remain bases, including punctuation.
    if 'GDEF' not in font:
        font['GDEF'] = newTable('GDEF')
        font['GDEF'].table = otTables.GDEF()
        font['GDEF'].table.Version = 0x00010000
        font['GDEF'].table.AttachList = None
        font['GDEF'].table.LigCaretList = None
        font['GDEF'].table.MarkAttachClassDef = None
    classes = otTables.ClassDef()
    classes.classDefs = {name: 2 if name in arabic_names else 1 for name in glyph_map}
    font['GDEF'].table.GlyphClassDef = classes
    groups = {}
    for spelling, width in source_widths.items():
        groups.setdefault((CELL - width) // 2, []).append(token_name(spelling) + '.top')
    gap_coverages = {gap: buildCoverage(names, glyph_map) for gap, names in groups.items()}
    table = font['GPOS'].table
    lookups = table.LookupList.Lookup
    contextual_indices = []
    for preceding in (True, False):
        shift_indices = {}
        for gap in sorted(groups):
            shift_indices[gap] = len(lookups)
            value = buildValue({'XPlacement': -gap if preceding else gap})
            lookups.append(buildLookup(buildSinglePos({name: value for name in top_names}, glyph_map),
                                       table='GPOS', extension=True))
        for distance in range(1, MAX_TOKENS):
            subtables = []
            for gap in sorted(groups):
                context = [top_coverage] * (distance - 1) + [gap_coverages[gap]]
                subtable = otTables.ChainContextPos()
                subtable.Format = 3
                subtable.BacktrackCoverage = context if preceding else []
                subtable.BacktrackGlyphCount = len(subtable.BacktrackCoverage)
                subtable.InputCoverage = [top_coverage]
                subtable.InputGlyphCount = 1
                subtable.LookAheadCoverage = [] if preceding else context
                subtable.LookAheadGlyphCount = len(subtable.LookAheadCoverage)
                record = otTables.PosLookupRecord()
                record.SequenceIndex = 0
                record.LookupListIndex = shift_indices[gap]
                subtable.PosLookupRecord = [record]
                subtable.PosCount = 1
                subtables.append(subtable)
            contextual_indices.append(len(lookups))
            lookups.append(buildLookup(subtables, flags=4, table='GPOS', extension=True))
    table.LookupList.LookupCount = len(lookups)
    for record in table.FeatureList.FeatureRecord:
        if record.FeatureTag == 'kern':
            record.Feature.LookupListIndex.extend(contextual_indices)
            record.Feature.LookupCount = len(record.Feature.LookupListIndex)


def build_font(output=HERE / 'arabizi-font.ttf'):
    output = Path(output)
    if output.resolve() == BASE.resolve():
        raise ValueError('Output must not overwrite the source font')
    with TTFont(BASE) as variable:
        base = instantiateVariableFont(variable, {'wght': 400}, inplace=False)
    glyphset = base.getGlyphSet()
    cmap = base.getBestCmap()
    source_advances = annotation_advances(base)
    source_widths = {s: sum(source_advances[c] for c in s) for s in TOKENS}
    outlines, metrics = {}, {}

    def glyph(name, drawings, advance):
        pen = TTGlyphPen(None)
        for original, transform in drawings:
            recording = DecomposingRecordingPen(glyphset)
            glyphset[original].draw(recording)
            recording.replay(TransformPen(pen, transform))
        outlines[name] = pen.glyph()
        metrics[name] = (advance, getattr(outlines[name], 'xMin', 0))

    glyph('.notdef', [(cmap[63], (1, 0, 0, 1, 0, 0))], CELL)
    for cp in range(32, 127):
        original = cmap[cp]
        glyph(f'u{cp:04x}', [(original, (1, 0, 0, 1, 0, 0))], base['hmtx'][original][0])
    # Each Arabic outline is sampled once, including positioned dot components.
    forms = {(char, form): sample_form(char, form)
             for char in sorted(set(TOKENS.values())) for form in ('isol', 'init', 'medi', 'fina')}
    for spelling, char in TOKENS.items():
        name = token_name(spelling)
        width = sum(base['hmtx'][cmap[ord(c)]][0] for c in spelling)
        # Source annotations always read LTR; the Arabic row moves independently.
        for suffix, scale, x, y, advance in [('top', ANNOTATION_SCALE, -CELL + (CELL - source_widths[spelling]) / 2, 1180, 0),
                                              ('raw', 1, 0, 0, width),
                                              ('token', 1, 0, 0, CELL)]:
            drawings = []
            for c in spelling:
                original = cmap[ord(c)]
                drawings.append((original, (scale, 0, 0, scale, x, y)))
                x += source_advances[c] if suffix == 'top' else base['hmtx'][original][0] * scale
            glyph(name + '.' + suffix, drawings, advance)
        for form in ('isol', 'init', 'medi', 'fina'):
            shaped = forms[char, form]
            width = sum(item['ax'] for item in shaped)
            sx = CELL / max(width, 1)
            x = 0
            drawings = []
            for item in shaped:
                drawings.append((item['g'], (sx, 0, 0, 1, (x + item['dx']) * sx, item['dy'])))
                x += item['ax']
            glyph(name + '.' + form, drawings, CELL)

    for spelling, arabic in WORDS.items():
        shaped = json.loads(subprocess.check_output([
            'hb-shape', str(BASE), '--text=' + arabic, '--direction=rtl',
            '--script=arab', '--output-format=json'], text=True))
        arabic_width = sum(item['ax'] for item in shaped)
        source_width = sum(base['hmtx'][cmap[ord(c)]][0] for c in spelling) * .40
        width = round(max(arabic_width, source_width) + 160)
        drawings = []
        x = (width - arabic_width) / 2
        for item in shaped:
            drawings.append((item['g'], (1, 0, 0, 1, x + item['dx'], item['dy'])))
            x += item['ax']
        x = (width - source_width) / 2
        for c in spelling:
            original = cmap[ord(c)]
            drawings.append((original, (.40, 0, 0, .40, x, 1180)))
            x += base['hmtx'][original][0] * .40
        glyph('word.' + spelling, drawings, width)

    # Keep track coverages contiguous so their serialized ranges stay small.
    def track(name):
        suffix = name.rsplit('.', 1)[-1]
        return 0 if name == '.notdef' else 1 if name.startswith('u') else {'token': 2, 'raw': 3, 'top': 4, 'isol': 5, 'init': 5, 'medi': 5, 'fina': 5}.get(suffix, 6)
    names = sorted(outlines, key=track)
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(names)
    fb.setupCharacterMap({cp: f'u{cp:04x}' for cp in range(32, 127)})
    fb.setupGlyf(outlines)
    # Compute true sidebearings, including negative annotation bearings.
    for name, outline in outlines.items():
        outline.recalcBounds(fb.font['glyf'])
        metrics[name] = (metrics[name][0], getattr(outline, 'xMin', 0))
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=1600, descent=-500)
    fb.setupOS2(sTypoAscender=1600, sTypoDescender=-500, sTypoLineGap=0,
                usWinAscent=1600, usWinDescent=500, fsType=0, fsSelection=0x40)
    fb.setupNameTable({'familyName': 'Arabizi Annotated', 'styleName': 'Regular',
                       'uniqueFontIdentifier': 'ArabiziAnnotated-1.001',
                       'fullName': 'Arabizi Annotated Regular', 'psName': 'ArabiziAnnotated-Regular',
                       'version': 'Version 1.001',
                       'copyright': 'Copyright 2022 The Noto Project Authors. Copyright 2026 Michael Brackx. Arabizi modifications.',
                       'licenseDescription': 'This Font Software is licensed under the SIL Open Font License, Version 1.1.',
                       'licenseInfoURL': 'https://openfontlicense.org/'})
    fb.setupPost()
    fb.setupMaxp()
    fb.font['head'].created = fb.font['head'].modified = 3864672000
    tokens = [token_name(s) for s in TOKENS]
    cls = lambda values: '[' + ' '.join(values) + ']'
    fea = ['languagesystem DFLT dflt;', 'languagesystem latn dflt;',
           '@TOKEN = ' + cls(t + '.token' for t in tokens) + ';',
           '@RAW = ' + cls(t + '.raw' for t in tokens) + ';',
           '@ANY = [@TOKEN @RAW];']
    for suffix in ('isol', 'init', 'medi', 'fina'):
        fea.append('@' + suffix.upper() + ' = ' + cls(t + '.' + suffix for t in tokens) + ';')
    fea += ['@AR = [@ISOL @INIT @MEDI @FINA];', '@TOP = ' + cls(t + '.top' for t in tokens) + ';']
    fea.append('@LETTER = ' + cls(f'u{ord(c):04x}' for c in SINGLES) + ';')
    word_lookups = []
    for index, spelling in enumerate(sorted(WORDS, key=lambda s: (-len(s), s))):
        sequence = [f'u{ord(c):04x}' for c in spelling]
        action, guard = f'WORD_{index}', f'GUARD_{index}'
        context = sequence[0] + "' " + ' '.join(sequence[1:])
        fea += [f'lookup {action} {{ sub ' + ' '.join(sequence) + f' by word.{spelling}; }} {action};',
                f'lookup {guard} {{', f'ignore sub @LETTER {context};',
                f'ignore sub {context} @LETTER;',
                f"sub {sequence[0]}' lookup {action} " + ' '.join(sequence[1:]) + ';',
                f'}} {guard};']
        word_lookups.append(guard)
    # Longest spellings win before single-character substitutions.
    fea.append('lookup TOKENIZE {')
    for spelling in sorted(TOKENS, key=lambda s: (-len(s), s)):
        fea.append('sub ' + ' '.join(f'u{ord(c):04x}' for c in spelling) + ' by ' + token_name(spelling) + '.token;')
    fea.append('} TOKENIZE;')
    # Preserve overlong words as Latin, instead of allowing positioned overlaps.
    fea.append('lookup OVERFLOW {')
    for before in range(MAX_TOKENS + 1):
        fea.append('sub ' + ' '.join(['@ANY'] * before + ["@TOKEN'"] + ['@ANY'] * (MAX_TOKENS - before)) + ' by @RAW;')
    fea.append('} OVERFLOW;')
    # Select joining forms while the tokens are still in logical input order.
    fea += ['lookup ISOLATE { sub @TOKEN by @ISOL; } ISOLATE;']
    left = [token_name(s) + '.' + form for s, c in TOKENS.items() if c in DUAL for form in ('isol', 'init', 'medi', 'fina')]
    right = [token_name(s) + '.' + form for s, c in TOKENS.items() if c in RIGHT for form in ('isol', 'init', 'medi', 'fina')]
    fea += ['@CONNECT_NEXT = ' + cls(left) + ';', '@CONNECT_PREV = ' + cls(right) + ';',
            'lookup JOIN {']
    for spelling, char in TOKENS.items():
        t = token_name(spelling)
        if char in DUAL:
            fea.append(f'sub @CONNECT_NEXT {t}.isol\' @CONNECT_PREV by {t}.medi;')
            fea.append(f'sub {t}.isol\' @CONNECT_PREV by {t}.init;')
        if char in RIGHT:
            fea.append(f'sub @CONNECT_NEXT {t}.isol\' by {t}.fina;')
    fea.append('} JOIN;')
    fea.append('lookup ANNOTATE {')
    for t in tokens:
        for form in ('isol', 'init', 'medi', 'fina'):
            fea.append(f'sub {t}.{form} by {t}.{form} {t}.top;')
    fea += ['} ANNOTATE;', 'feature rlig { ' + ' '.join(f'lookup {name};' for name in word_lookups) + ' lookup TOKENIZE; lookup OVERFLOW; lookup ISOLATE; lookup JOIN; lookup ANNOTATE; } rlig;']
    # The Arabic row is reflected within each word; the source row stays LTR.
    # Separate GPOS lookups add the following and preceding token counts.
    for side in ('AFTER', 'BEFORE'):
        fea.append(f'lookup {side} useExtension {{')
        for count in range(MAX_TOKENS - 1, 0, -1):
            context = ['@TOP', '@AR'] * count if side == 'AFTER' else ['@AR', '@TOP'] * count
            value = count * CELL * (1 if side == 'AFTER' else -1)
            target = f"@AR' <{value} 0 0 0>"
            rule = [target] + context if side == 'AFTER' else context + [target]
            fea.append('pos ' + ' '.join(rule) + ';')
        fea.append(f'}} {side};')
    fea += ['feature kern { lookup AFTER; lookup BEFORE; } kern;']
    addOpenTypeFeaturesFromString(fb.font, '\n'.join(fea))
    compact_annotations(fb.font, source_widths)
    output.parent.mkdir(parents=True, exist_ok=True)
    fb.font.save(output, reorderTables=False)
    base.close()
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE / 'arabizi-font.ttf')
    args = parser.parse_args()
    print('Saved', build_font(args.output))
