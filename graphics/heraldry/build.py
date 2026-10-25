# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Build Heraldry: a bounded blazon parser and colour shield compositor in GSUB."""

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys
import unicodedata

import pathops
from fontTools.colorLib.builder import buildCOLR, buildCPAL
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.svgLib.path import parse_path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from decoders.shared.font_metadata import (DEFAULT_BASE, load_base_font,
                                          mark_modified_font, replace_font_names)

FAMILY = 'Heraldry'
TINCTURES = dict(or_='#efbf4b', argent='#f5f2e5', azure='#205aa4',
                gules='#c5363c', sable='#20212a', vert='#237453', purpure='#783f83')
# Python's reserved word is only escaped in the palette dictionary.
TINCTURES = {key.rstrip('_'): value for key, value in TINCTURES.items()}
DIVISIONS = ('per pale', 'per fess', 'per bend', 'per bend sinister',
             'per chevron', 'per saltire', 'quarterly')
ORDINARIES = ('chief', 'fess', 'pale', 'bend', 'bend sinister', 'chevron',
              'cross', 'saltire', 'bordure')
CHARGES = {'mullet': 'mullets', 'lozenge': 'lozenges', 'crescent': 'crescents',
           'heart': 'hearts', 'fleur-de-lis': 'fleurs-de-lis',
           'lion rampant': 'lions rampant'}


def ident(text):
    return text.replace('-', '_').replace(' ', '_')


def polygon(points):
    result = pathops.Path()
    result.moveTo(*points[0])
    for point in points[1:]:
        result.lineTo(*point)
    result.close()
    return result


def rect(x, y, width, height):
    return polygon(((x, y), (x+width, y), (x+width, y+height), (x, y+height)))


def ellipse(x, y, rx, ry=None):
    ry = rx if ry is None else ry
    k = .5522847498
    result = pathops.Path()
    result.moveTo(x+rx, y)
    result.cubicTo(x+rx, y+k*ry, x+k*rx, y+ry, x, y+ry)
    result.cubicTo(x-k*rx, y+ry, x-rx, y+k*ry, x-rx, y)
    result.cubicTo(x-rx, y-k*ry, x-k*rx, y-ry, x, y-ry)
    result.cubicTo(x+k*rx, y-ry, x+rx, y-k*ry, x+rx, y)
    result.close()
    return result


def combine(*shapes):
    result = pathops.Path()
    for shape in shapes:
        result = pathops.op(result, shape, pathops.PathOp.UNION)
    return result


def curved_path(data):
    result = pathops.Path()
    parse_path(data, result.getPen())
    return result


def stroke(shape, width):
    result = pathops.Path(shape)
    result.stroke(width, pathops.LineCap.ROUND_CAP, pathops.LineJoin.ROUND_JOIN, 4)
    result.convertConicsToQuads(.05)
    return pathops.simplify(result)


def shield():
    result = pathops.Path()
    result.moveTo(100, 960)
    result.lineTo(900, 960)
    result.lineTo(900, 560)
    result.cubicTo(900, 320, 700, 160, 500, 40)
    result.cubicTo(300, 160, 100, 320, 100, 560)
    result.close()
    return result


def partition(division):
    """Region occupied by the second tincture; first is chief/dexter."""
    if division == 'per pale':
        return rect(500, -100, 600, 1200)
    if division == 'per fess':
        return rect(-100, -100, 1200, 600)
    if division == 'per bend':
        return polygon(((-100, -100), (-100, 1100), (1100, -100)))
    if division == 'per bend sinister':
        return polygon(((-100, -100), (1100, 1100), (1100, -100)))
    if division == 'per chevron':
        return polygon(((-100, -100), (1100, -100), (1100, 220),
                        (500, 700), (-100, 220)))
    if division == 'per saltire':
        return combine(polygon(((-100, -100), (-100, 1100), (500, 500))),
                       polygon(((1100, -100), (500, 500), (1100, 1100))))
    if division == 'quarterly':
        return combine(rect(500, 500, 600, 600), rect(-100, -100, 600, 600))
    raise ValueError(division)


def ordinary(name):
    bend = polygon(((-150, 1010), (-10, 1150), (1150, -10), (1010, -150)))
    if name == 'chief':
        return rect(-100, 740, 1200, 360)
    if name == 'fess':
        return rect(-100, 430, 1200, 220)
    if name == 'pale':
        return rect(390, -100, 220, 1200)
    if name == 'bend':
        return bend
    if name == 'bend sinister':
        return bend.transform(-1, 0, 0, 1, 1000, 0)
    if name == 'chevron':
        return polygon(((-100, 220), (500, 700), (1100, 220),
                        (1100, 440), (500, 920), (-100, 440)))
    if name == 'cross':
        return combine(ordinary('fess'), ordinary('pale'))
    if name == 'saltire':
        return combine(bend, ordinary('bend sinister'))
    if name == 'bordure':
        return pathops.op(shield(), shield().transform(.77, 0, 0, .77, 115, 115),
                          pathops.PathOp.DIFFERENCE)
    raise ValueError(name)


def charge(name):
    """Original silhouettes in a roughly 460-unit square, centred at the origin."""
    if name == 'mullet':
        return polygon([(math.cos(math.pi/2+i*math.pi/5)*r,
                         math.sin(math.pi/2+i*math.pi/5)*r)
                        for i, r in enumerate([230, 92]*5)])
    if name == 'lozenge':
        return polygon(((0, 240), (-170, 0), (0, -240), (170, 0)))
    if name == 'crescent':
        return pathops.op(ellipse(0, 0, 210), ellipse(0, 105, 185),
                          pathops.PathOp.DIFFERENCE)
    if name == 'heart':
        p = pathops.Path()
        p.moveTo(0, -220)
        p.cubicTo(-340, 10, -185, 290, 0, 130)
        p.cubicTo(185, 290, 340, 10, 0, -220)
        p.close()
        return p
    if name == 'fleur-de-lis':
        centre = pathops.Path()
        centre.moveTo(0, 250)
        centre.cubicTo(-115, 100, -55, 50, -25, -95)
        centre.lineTo(25, -95)
        centre.cubicTo(55, 50, 115, 100, 0, 250)
        centre.close()
        wing = pathops.Path()
        wing.moveTo(25, -90)
        wing.cubicTo(55, 100, 235, 145, 225, 0)
        wing.cubicTo(220, -85, 125, -95, 130, -25)
        wing.cubicTo(170, -65, 165, 45, 115, 10)
        wing.cubicTo(75, -10, 75, -65, 70, -90)
        wing.close()
        foot = polygon(((-30, -110), (-80, -220), (0, -180),
                        (80, -220), (30, -110)))
        return combine(centre, wing, wing.transform(-1, 0, 0, 1, 0, 0),
                       rect(-100, -120, 200, 40), foot)
    if name == 'lion rampant':
        # Original dexter-facing lion: curved chest and haunch, open jaws,
        # scalloped mane, separate raised forepaws, claws and a tufted S-tail.
        body = curved_path('''M -58 145 C -22 158 22 123 34 83
            C 47 52 46 13 67 -20 C 96 -52 94 -83 67 -111
            C 47 -134 5 -130 -20 -111 C -39 -97 -58 -73 -53 -47
            C -49 -26 -58 -9 -82 16 C -105 40 -101 83 -83 111 Z''')
        mane = curved_path('''M -145 246 C -133 282 -89 293 -58 276
            C -34 282 -7 269 -6 246 C 24 236 32 209 18 187
            C 44 170 36 143 15 136 C 28 115 13 92 -11 95
            L -4 77 C -32 76 -54 91 -65 110
            C -95 99 -116 119 -112 140 C -143 143 -150 167 -137 185
            C -158 198 -161 225 -145 246 Z''')
        head = curved_path('''M -124 225 C -145 231 -157 217 -158 202
            L -195 197 L -202 180 L -193 168 L -163 169
            C -151 165 -149 153 -162 151 L -187 154 L -194 142
            L -181 130 L -155 129 C -139 134 -133 145 -118 149
            C -93 148 -79 174 -87 197 L -93 220 Z''').transform(1, 0, 0, 1, -5, 40)
        fore = curved_path('''M -60 105 C -94 113 -113 124 -126 154
            L -153 235 C -159 251 -177 258 -194 250
            L -220 263 L -228 254 L -211 241 L -236 247
            L -241 236 L -216 227 L -239 226 L -238 214
            L -211 213 C -187 198 -177 199 -171 213 L -158 153
            C -148 108 -111 75 -71 56 Z''').transform(1, 0, 0, .65, 0, 0)
        lower_fore = curved_path('''M -72 65 C -110 63 -126 63 -143 88
            L -160 119 L -187 131 L -214 137 L -221 127 L -202 117
            L -226 119 L -228 107 L -205 101 L -227 97 L -224 86
            L -198 90 C -182 80 -173 81 -167 91 L -152 55
            C -136 24 -104 14 -74 20 Z''').transform(1, 0, 0, 1, 0, -30)
        hind = curved_path('''M 50 -64 C 116 -61 144 -97 116 -137
            L 78 -191 L 95 -218 L 146 -228 L 152 -243 L 132 -249
            L 73 -244 L 48 -222 C 35 -207 39 -189 48 -174 L 76 -127
            C 42 -139 12 -123 8 -97 Z''')
        other_hind = curved_path('''M -8 -65 C -45 -87 -57 -106 -58 -134
            L -82 -160 L -132 -170 L -174 -159 L -187 -167
            L -177 -179 L -191 -181 L -188 -193 L -164 -195
            L -174 -204 L -165 -213 L -130 -202 L -75 -192
            C -44 -184 -26 -165 -22 -139 L 19 -103 Z''')
        tail = curved_path('''M 72 -58 C 171 -38 112 46 141 83
            C 166 114 207 105 211 142 C 216 174 175 187 183 219
            C 188 239 216 241 234 229''')
        tuft = curved_path('''M 214 232 C 202 252 222 270 246 281
            C 237 266 249 260 244 241 C 237 224 225 218 214 232 Z''')
        tongue = curved_path('M -177 155 C -207 145 -216 153 -211 166').transform(1, 0, 0, 1, -5, 40)
        silhouette = combine(body, mane, head, fore, lower_fore, hind, other_hind,
                             stroke(tail, 18), tuft, stroke(tongue, 9),
                             ellipse(-80, 278, 20, 24))
        mane_detail = curved_path('M -42 255 C 4 230 8 171 -26 150')
        haunch_detail = curved_path('M 62 -85 C 93 -90 90 -109 74 -118')
        details = combine(ellipse(-133, 239, 8, 6), ellipse(-80, 279, 9, 11),
                          stroke(mane_detail, 6), stroke(haunch_detail, 6))
        return pathops.op(silhouette, details, pathops.PathOp.DIFFERENCE)
    raise ValueError(name)


def geometry_glyph(shape, scale):
    pen = TTGlyphPen(None)
    shape.transform(scale, 0, 0, scale, 0, 0).draw(Cu2QuPen(pen, max_err=.5))
    return pen.glyph()


def vocabulary():
    phrases = [*DIVISIONS, *ORDINARIES, *CHARGES, *CHARGES.values(),
               *TINCTURES, 'a', 'three', 'and']
    return sorted({word for phrase in phrases for word in phrase.split()})


def build_font(output=HERE / 'heraldry-font.ttf', *, base=DEFAULT_BASE):
    output = Path(output)
    if output.suffix.lower() != '.ttf':
        raise ValueError('Output must have a .ttf extension')
    # Sidecars must not overwrite the source through a shared stem, symlink or
    # hard link. Check every destination before creating directories or writing.
    protected = [Path(base)]
    for target in [output, *(output.with_suffix(ext) for ext in ('.woff2', '.fea', '.json'))]:
        for other in protected:
            if (target.resolve() == other.resolve() or
                    (target.exists() and other.exists() and target.samefile(other))):
                raise ValueError('Output files must differ from the base and one another')
        protected.append(target)
    font = load_base_font(base, output)
    # A WOFF/WOFF2 source can contain TrueType outlines, but the installable
    # output must always be an uncompressed SFNT, regardless of input wrapper.
    font.flavor = None
    for tag in ('GSUB', 'GPOS', 'GDEF', 'DSIG'):
        if tag in font:
            del font[tag]
    upem = font['head'].unitsPerEm
    scale = upem / 1000
    order = list(font.getGlyphOrder())
    cmap = font.getBestCmap()
    palette = list(TINCTURES.values())
    ink = list(TINCTURES).index('sable')
    colors, layer_cache = {}, {}

    def put(name, glyph, width=0):
        if name in order:
            raise ValueError('Glyph collision: ' + name)
        glyph.recalcBounds(font['glyf'])
        font['glyf'][name] = glyph
        font['hmtx'][name] = (width, getattr(glyph, 'xMin', 0))
        order.append(name)

    def empty(name, width=0):
        put(name, TTGlyphPen(None).glyph(), width)

    def text_glyph(name, text):
        pen = TTGlyphPen(font.getGlyphSet())
        x = 0
        for char in text:
            glyph = cmap[ord(char)]
            pen.addComponent(glyph, (1, 0, 0, 1, x, 0))
            x += font['hmtx'][glyph][0]
        put(name, pen.glyph(), x)

    def picture(name, fallback, layers, width=0):
        put(name, geometry_glyph(fallback, scale), width)
        values = []
        for shape, color in layers:
            glyph = geometry_glyph(shape, scale)
            key = glyph.compile(font['glyf'])
            if key not in layer_cache:
                component = f'herald_layer_{len(layer_cache)}'
                put(component, glyph)
                layer_cache[key] = component
            values.append((layer_cache[key], color))
        colors[name] = values

    # Lexical ligatures preserve the exact original text outlines and advances.
    # They only become invisible canonical tokens after a WHOLE blazon validates.
    words = vocabulary()
    classes, matches, lexing, canonical, active = [], [], {}, [], []
    word_characters = {g for cp, g in cmap.items()
                       if unicodedata.category(chr(cp))[0] in 'LNM'}
    word_characters.update(cmap[ord(c)] for c in "_'-’" if ord(c) in cmap)
    classes.append('@word = [' + ' '.join(sorted(word_characters)) + '];')
    for word in words:
        variants = sorted({word, word.capitalize(), word.upper()})
        names = []
        target = 'tok_' + ident(word)
        empty(target)
        for i, text in enumerate(variants):
            name = f'lex_{ident(word)}_{i}'
            text_glyph(name, text)
            names.append(name)
            # Once lexed, a word must still block adjacent lexical matches.
            word_characters.add(name)
            match = 'LEX_' + ident(word) + '_' + str(i)
            raw = [cmap[ord(c)] for c in text]
            matches.append(f'lookup {match} {{ sub {" ".join(raw)} by {name}; }} {match};')
            marked = ' '.join(c+"'" for c in raw)
            applied = raw[0]+"' lookup "+match+' '+ ' '.join(c+"'" for c in raw[1:])
            lexing.setdefault(len(text), []).extend((f'ignore sub @word {marked};',
                          f'ignore sub {marked} @word;', f'sub {applied};'))
        classes.append('@w_'+ident(word)+' = ['+' '.join(names)+'];')
        canonical.append('sub ['+' '.join(names)+'] by '+target+';')
    classes[0] = '@word = [' + ' '.join(sorted(word_characters)) + '];'
    # One, two or three ordinary spaces; NBSP also works as a single gap.
    gaps = [cmap[32]]
    if 160 in cmap:
        gaps.append(cmap[160])
    for n in (3, 2):
        name = f'lex_gap_{n}'
        text_glyph(name, ' '*n)
        gaps.append(name)
        matches.append(f'lookup GAP_{n} {{ sub '+ ' '.join([cmap[32]]*n)+
                       f' by {name}; }} GAP_{n};')
        active.append(f'lookup GAP_{n};')
    classes.append('@gap = [' + ' '.join(dict.fromkeys(gaps)) + '];')
    empty('tok_gap')
    canonical.append('sub @gap by tok_gap;')
    empty('valid_begin')
    # End glyph owns the whole advance and paints the rim after all other layers.
    mask = shield()
    picture('shield_end', stroke(mask, 14), [(stroke(mask, 14), ink)], upem)
    classes.append('@tincture = ['+' '.join('@w_'+key for key in TINCTURES)+'];')

    def lexical(phrase):
        return list(itertools.chain.from_iterable(
            (["@gap"] if i else [])+['@w_'+ident(word)]
            for i, word in enumerate(phrase.split())))

    fields = [(['@tincture'], None)] + [
        (lexical(division)+['@gap', '@tincture', '@gap', '@w_and', '@gap', '@tincture'], division)
        for division in DIVISIONS]
    elements = [(lexical('a '+name)+['@gap', '@tincture'], name, 1)
                for name in (*ORDINARIES, *CHARGES)] + [
        (lexical('three '+plural)+['@gap', '@tincture'], name, 3)
        for name, plural in CHARGES.items()]
    comma = cmap[ord(',')]
    left, right = cmap[ord('[')], cmap[ord(']')]
    validation = []
    for field, _ in fields:
        tails = [[]] + [sep+element for element, _, _ in elements
                        for sep in ([comma, '@gap'], [comma], ['@gap'])]
        for tail in tails:
            values = [left+"' lookup BEGIN"]
            for token in field+tail:
                values.append(token+"'"+(' lookup CANONICAL' if token != comma else ''))
            values.append(right+"' lookup END")
            validation.append('sub '+' '.join(values)+';')

    def tokens(phrase):
        return ' tok_gap '.join('tok_'+ident(word) for word in phrase.split())

    field_rules = []
    for first in TINCTURES:
        name = 'field_'+first
        picture(name, pathops.Path(), [(mask, list(TINCTURES).index(first))])
        field_rules.append(f'sub valid_begin tok_{first} by {name};')
    for division in DIVISIONS:
        region = pathops.op(mask, partition(division), pathops.PathOp.INTERSECTION)
        boundary = pathops.op(mask, stroke(region, 8), pathops.PathOp.INTERSECTION)
        for first, second in itertools.product(TINCTURES, repeat=2):
            name = f'field_{ident(division)}_{first}_{second}'
            picture(name, boundary, [(mask, list(TINCTURES).index(first)),
                                     (region, list(TINCTURES).index(second))])
            field_rules.append(f'sub valid_begin {tokens(division)} tok_gap tok_{first} '
                               f'tok_gap tok_and tok_gap tok_{second} by {name};')
    element_rules = []
    for _, name, count in elements:
        if name in ORDINARIES:
            art = ordinary(name)
        else:
            shape = charge(name)
            placements = [(1, 500, 535)] if count == 1 else [(.43, 320, 735),
                                                           (.43, 680, 735), (.43, 500, 365)]
            art = combine(*(shape.transform(size, 0, 0, size, x, y)
                            for size, x, y in placements))
        art = pathops.op(mask, art, pathops.PathOp.INTERSECTION)
        edge = pathops.op(mask, stroke(art, 9), pathops.PathOp.INTERSECTION)
        phrase = 'a '+name if count == 1 else 'three '+CHARGES[name]
        for color in TINCTURES:
            target = f'device_{ident(name)}_{count}_{color}'
            picture(target, edge, [(art, list(TINCTURES).index(color)), (edge, ink)])
            for sep in (comma+' tok_gap ', comma+' ', 'tok_gap '):
                element_rules.append(f'sub {sep}{tokens(phrase)} tok_gap tok_{color} by {target};')

    lookups = []
    for length, rules in sorted(lexing.items(), reverse=True):
        name = 'WORDS_'+str(length)
        lookups.extend([f'lookup {name} useExtension {{', *rules, f'}} {name};'])
        active.append(f'lookup {name};')
    source = '\n'.join(['languagesystem DFLT dflt;', 'languagesystem latn dflt;',
        *classes, *matches, *lookups,
        'lookup BEGIN { sub '+left+' by valid_begin; } BEGIN;',
        'lookup END { sub '+right+' by shield_end; } END;',
        'lookup CANONICAL {', *canonical, '} CANONICAL;',
        'lookup VALIDATE useExtension {', *validation, '} VALIDATE;',
        'lookup FIELDS useExtension {', *field_rules, '} FIELDS;',
        'lookup DEVICES useExtension {', *element_rules, '} DEVICES;',
        'feature liga {', *active, 'lookup VALIDATE;', 'lookup FIELDS;',
        'lookup DEVICES;', '} liga;'])+'\n'
    font.setGlyphOrder(order)
    font['COLR'] = buildCOLR(colors, version=0, glyphMap=font.getReverseGlyphMap())
    font['CPAL'] = buildCPAL([[tuple(int(c[i:i+2], 16)/255 for i in (1, 3, 5))+(1.,)
                              for c in palette]])
    addOpenTypeFeaturesFromString(font, source)
    font['hhea'].ascent = max(font['hhea'].ascent, upem)
    font['hhea'].descent = min(font['hhea'].descent, -round(.2*upem))
    for attr, value in (('sTypoAscender', font['hhea'].ascent),
                        ('sTypoDescender', font['hhea'].descent), ('sTypoLineGap', 0),
                        ('usWinAscent', font['hhea'].ascent),
                        ('usWinDescent', -font['hhea'].descent), ('fsType', 0)):
        setattr(font['OS/2'], attr, value)
    font['head'].fontRevision = 1.001
    replace_font_names(font, {1:FAMILY, 2:'Regular', 3:FAMILY+' 1.001', 4:FAMILY+' Regular',
                              5:'Version 1.001', 6:'Heraldry-Regular', 16:FAMILY, 17:'Regular'})
    mark_modified_font(font, FAMILY, kind='heraldry font')
    font.recalcTimestamp = False
    font['head'].created = font['head'].modified = 3785270400
    output.parent.mkdir(parents=True, exist_ok=True)
    font.save(output)
    font.flavor = 'woff2'
    font.save(output.with_suffix('.woff2'))
    output.with_suffix('.fea').write_text(source)
    info = dict(family=FAMILY, tinctures=TINCTURES, divisions=list(DIVISIONS),
                ordinaries=list(ORDINARIES), charges=CHARGES,
                grammar='[FIELD] or [FIELD, a DEVICE TINCTURE] or [FIELD, three CHARGES TINCTURE]',
                field_glyphs=7+len(DIVISIONS)*49, device_glyphs=len(elements)*7,
                glyphs=len(order), units_per_em=upem, shield_advance=upem,
                palette_colors=len(palette), color_glyphs=len(colors),
                unique_layer_glyphs=len(layer_cache),
                combinations=(7+len(DIVISIONS)*49)*(1+len(elements)*7),
                ttf_bytes=output.stat().st_size,
                woff2_bytes=output.with_suffix('.woff2').stat().st_size,
                sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                font_license='Apache-2.0', artwork_license='Apache-2.0')
    output.with_suffix('.json').write_text(json.dumps(info, indent=2)+'\n')
    print(json.dumps({key: info[key] for key in ('family', 'glyphs', 'combinations',
                                               'ttf_bytes', 'woff2_bytes')}, indent=2))
    return info


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE / 'heraldry-font.ttf')
    parser.add_argument('--base', type=Path, default=DEFAULT_BASE)
    args = parser.parse_args()
    build_font(args.output, base=args.base)
