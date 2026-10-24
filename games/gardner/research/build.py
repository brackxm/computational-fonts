# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Rebuild the frozen research font. No engine, corpus extraction or proof search."""
import argparse
import lzma
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.DefaultTable import DefaultTable

HERE = Path(__file__).resolve().parent


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def check_inputs(manifest):
    missing = [name for name in manifest['inputs'] if not (HERE / name).is_file()]
    if missing:
        raise ValueError('Missing frozen research inputs: ' + ', '.join(missing) +
                         '. Run python3 games/gardner/research/restore_inputs.py first; '
                         'see the research readme for the local artifact branch.')
    for name, expected in manifest['inputs'].items():
        path = HERE / name
        if sha256(path) != expected['sha256'] or path.stat().st_size != expected['bytes']:
            raise ValueError(f'Frozen input mismatch: {name}')


def glyph_order(meta):
    with TTFont(HERE / 'inputs/game-base.ttf', lazy=True) as font:
        order = font.getGlyphOrder()
    if len(order) != meta['base_glyph_count']:
        raise ValueError('Base glyph count mismatch')
    return order + ['packed_' + str(gid) for gid in range(len(order), meta['glyph_count'])]


def bake(stem, manifest):
    meta = json.loads(stem.with_suffix('.json').read_text())
    order = glyph_order(meta)
    with tempfile.TemporaryDirectory(prefix='.gardner-font-', dir=stem.parent) as directory:
        draft = Path(directory) / 'font.ttf'
        with TTFont(HERE / 'inputs/game-base.ttf', recalcTimestamp=False) as font:
            empty = TTGlyphPen(None).glyph()
            for name in order[meta['base_glyph_count']:]:
                font['glyf'].glyphs[name] = empty
                font['hmtx'].metrics[name] = (0, 0)
            font.setGlyphOrder(order)
            for tag, suffix in [('GSUB', '.gsub'), ('GDEF', '.gdef')]:
                table = DefaultTable(tag)
                table.data = stem.with_suffix(suffix).read_bytes()
                font[tag] = table
            family = manifest['font_family']
            postscript = ''.join(c for c in family if c.isascii() and c.isalnum())[:63]
            for name_id, value in [(1, family), (3, postscript), (4, family), (6, postscript)]:
                for record in tuple(font['name'].names):
                    if record.nameID == name_id:
                        font['name'].setName(value, name_id, record.platformID, record.platEncID, record.langID)
                font['name'].setName(value, name_id, 3, 1, 0x409)
            font['post'].formatType = 3.0
            font['head'].created, font['head'].modified = manifest['head_timestamps']
            font.save(draft)
        if sha256(draft) != manifest['font_sha256']:
            raise ValueError('Rebuilt font differs from the accepted artifact')
        draft.replace(stem.with_suffix('.ttf'))
    print('Rebuilt exact accepted font:', stem.with_suffix('.ttf'), flush=True)


def build(output):
    manifest = json.loads((HERE / 'manifest.json').read_text())
    check_inputs(manifest)
    output.mkdir(parents=True, exist_ok=True)
    tree = output / 'policy.tree'
    with lzma.open(HERE / 'inputs/policy.tree.xz', 'rb') as source, tree.open('wb') as target:
        shutil.copyfileobj(source, target)
    if sha256(tree) != manifest['policy_tree_sha256']:
        raise ValueError('Decompressed policy tree mismatch')
    with TTFont(HERE / 'inputs/game-base.ttf', lazy=True) as font:
        (output / 'base.gsub').write_bytes(font.getTableData('GSUB'))
    compiler = output / 'binary-font'
    subprocess.run(['clang++', '-std=c++17', '-O3', str(HERE / 'compiler/binary_font.cpp'), '-o', str(compiler)], check=True)
    stem = output / 'gardner-research'
    with (output / 'compiler.log').open('w') as log:
        subprocess.run([str(compiler.resolve()), str(tree.resolve()), str(stem.resolve()),
                        '6404', 'game', str(HERE / 'inputs/game-base.gamepack'),
                        str((output / 'base.gsub').resolve())], check=True, stdout=log, stderr=log)
    bake(stem, manifest)
    return stem


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=HERE / 'build')
    build(parser.parse_args().output_dir.resolve())
