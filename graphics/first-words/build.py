# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Build the First Words Pictures COLRv0 font; word recognition runs inside GSUB."""

import argparse
import hashlib
import json
from pathlib import Path
import string
import sys
import unicodedata
from zipfile import ZipFile, ZIP_DEFLATED

from fontTools.colorLib.builder import buildCOLR, buildCPAL
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString

from svg_to_font import layers_from_svg, glyph_from_path, monochrome_path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from decoders.shared.font_metadata import DEFAULT_BASE, load_base_font, mark_modified_font, replace_font_names

FAMILY = 'First Words Pictures'
DEFAULT_OUTPUT = HERE / 'first-words-font.ttf'


def spellings(drawing):
    label = drawing['label']
    values = {label}
    if ' ' in label:
        values.update((label.replace(' ', '-'), label.replace(' ', ''), label.replace(' ', '\u00a0')))
    return sorted(values)


def glyph_name(drawing):
    return 'picture_' + drawing['id'].replace('-', '_')


def feature_source(font, manifest):
    cmap = font.getBestCmap()
    classes = [f'@letter_{c} = [{cmap[ord(c)]} {cmap[ord(c.upper())]}];'
               for c in string.ascii_lowercase]
    # Protect both sides of words, including adjacent digits, combining marks,
    # apostrophes and hyphens. These are contexts in the same shaping run.
    word_glyphs = {g for code, g in cmap.items() if unicodedata.category(chr(code))[0] in 'LNM'}
    word_glyphs.update(cmap[ord(c)] for c in "_'’-‐‑" if ord(c) in cmap)
    classes.append('@word_char = [' + ' '.join(sorted(word_glyphs)) + '];')

    def pattern(text, marked=False):
        values = [f'@letter_{c}' if c in string.ascii_lowercase else cmap[ord(c)] for c in text]
        return ' '.join(v + ("'" if marked else '') for v in values)

    aliases = [(text, glyph_name(d)) for d in manifest['drawings'] for text in spellings(d)]
    aliases.sort(key=lambda item: (-len(item[0]), item[0]))
    lookups, guards = [], []
    for index, (text, target) in enumerate(aliases):
        name = f'MATCH_{index}'
        plain, marked = pattern(text), pattern(text, True)
        lookups.append(f'lookup {name} useExtension {{ sub {plain} by {target}; }} {name};')
        values = marked.split()
        values[0] += f' lookup {name}'
        guards.extend((f'ignore sub @word_char {marked};',
                       f'ignore sub {marked} @word_char;',
                       'sub ' + ' '.join(values) + ';'))
    return '\n'.join(['languagesystem DFLT dflt;', 'languagesystem latn dflt;',
                      *classes, *lookups,
                      'lookup WHOLE_WORDS useExtension {', *guards, '} WHOLE_WORDS;',
                      'feature liga { lookup WHOLE_WORDS; } liga;']) + '\n'


def build_font(output=DEFAULT_OUTPUT, *, base=DEFAULT_BASE):
    output = Path(output)
    manifest = json.loads((HERE / 'manifest.json').read_text())
    if manifest['count'] != 100 or len(manifest['drawings']) != 100:
        raise ValueError('Expected the reviewed 100-drawing collection')
    font = load_base_font(base, output)
    for tag in ('GSUB', 'GPOS', 'GDEF', 'DSIG'):
        if tag in font:
            del font[tag]
    upem = font['head'].unitsPerEm
    advance = round(upem * 1.12)
    order = list(font.getGlyphOrder())
    palette = [value.lower() for value in manifest['palette'].values()]
    palette_indices = {color: i for i, color in enumerate(palette)}
    colors, counts, cache = {}, {}, {}

    def put(name, glyph, width=0):
        if name in font['glyf']:
            raise ValueError(f'Glyph name collision: {name}')
        glyph.recalcBounds(font['glyf'])
        font['glyf'][name] = glyph
        font['hmtx'][name] = (width, getattr(glyph, 'xMin', 0))
        order.append(name)

    for drawing in manifest['drawings']:
        layers = layers_from_svg(HERE / drawing['file'], upem)
        target = glyph_name(drawing)
        colored = []
        for shape, color, _role in layers:
            if color not in palette_indices:
                raise ValueError(f'{drawing["id"]}: color not in the shared palette: {color}')
            glyph = glyph_from_path(shape)
            key = glyph.compile(font['glyf'])
            if key not in cache:
                component = f'art_layer_{len(cache)}'
                put(component, glyph)
                cache[key] = component
            colored.append((cache[key], palette_indices[color]))
        put(target, glyph_from_path(monochrome_path(layers)), advance)
        colors[target] = colored
        counts[drawing['id']] = len(colored)
    font.setGlyphOrder(order)
    font['COLR'] = buildCOLR(colors, version=0, glyphMap=font.getReverseGlyphMap())
    font['CPAL'] = buildCPAL([[tuple(int(color[i:i+2],16)/255 for i in (1,3,5)) + (1.,)
                              for color in palette]])
    source = feature_source(font, manifest)
    addOpenTypeFeaturesFromString(font, source)
    font['hhea'].ascent = max(font['hhea'].ascent, round(upem))
    font['hhea'].descent = min(font['hhea'].descent, -round(upem*.25))
    font['OS/2'].sTypoAscender = font['hhea'].ascent
    font['OS/2'].sTypoDescender = font['hhea'].descent
    font['OS/2'].sTypoLineGap = 0
    font['OS/2'].usWinAscent = max(font['OS/2'].usWinAscent, font['hhea'].ascent)
    font['OS/2'].usWinDescent = max(font['OS/2'].usWinDescent, -font['hhea'].descent)
    font['OS/2'].fsType = 0
    replace_font_names(font, {1:FAMILY, 2:'Regular', 3:FAMILY+' 1.0', 4:FAMILY+' Regular',
                              5:'Version 1.000', 6:'FirstWordsPictures-Regular',
                              16:FAMILY, 17:'Regular'})
    mark_modified_font(font, FAMILY, kind='picture-word font')
    font['name'].setName('100 original CC0 illustrations; COLRv0 vectors; whole-word ligatures. '
                         'Roboto text outlines and the compiled font retain Apache-2.0 licensing.',
                         10, 3, 1, 0x409)
    # Reproducible table timestamps; identity derives from geometry and GSUB.
    font.recalcTimestamp = False
    font['head'].created = font['head'].modified = 3785270400
    output.parent.mkdir(parents=True, exist_ok=True)
    font.save(output)
    font.flavor = 'woff2'
    web = output.with_suffix('.woff2')
    font.save(web)
    output.with_suffix('.fea').write_text(source)
    info = dict(family=FAMILY, images=len(colors), glyphs=len(order), palette_colors=len(palette),
                vector_layers=sum(counts.values()), unique_layer_glyphs=len(cache),
                units_per_em=upem, picture_advance=advance, ttf_bytes=output.stat().st_size,
                woff2_bytes=web.stat().st_size, spellings=sum(len(spellings(d)) for d in manifest['drawings']),
                font_license='Apache-2.0', artwork_license='CC0-1.0',
                sha256=hashlib.sha256(output.read_bytes()).hexdigest(), layers_per_image=counts)
    output.with_suffix('.json').write_text(json.dumps(info, indent=2)+'\n')
    vocabulary = [{key:d[key] for key in ('id', 'label', 'category')} for d in manifest['drawings']]
    output.with_name('vocabulary.js').write_text('// Generated from manifest.json. Original annotations: CC0-1.0.\n'
                                                'window.FIRST_WORDS = ' + json.dumps(vocabulary, ensure_ascii=False) + ';\n')
    output.with_name('words.txt').write_text('\n'.join(d['label'] for d in manifest['drawings']) + '\n')
    print(json.dumps({k:v for k,v in info.items() if k != 'layers_per_image'}, indent=2))
    return info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--base', type=Path, default=DEFAULT_BASE)
    args = parser.parse_args()
    build_font(args.output, base=args.base)
    archive = args.output.with_name('first-words-fonts.zip')
    with ZipFile(archive, 'w', ZIP_DEFLATED) as package:
        for file in (args.output, args.output.with_suffix('.woff2'), args.output.with_suffix('.json'),
                     args.output.with_name('words.txt')):
            package.write(file, file.name)
        for name in ('FONT_README.txt', 'FONT_LICENSE.txt', 'FONT_NOTICE.txt', 'LICENSE.txt'):
            package.write(HERE / name, name)
    print(f'Download bundle: {archive} ({archive.stat().st_size:,} bytes)')


if __name__ == '__main__':
    main()
