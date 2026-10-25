# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Extension sharing preserves complete layout data and interpreter clocks."""
from io import BytesIO, StringIO
import json
import shutil
import subprocess

import pytest
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.misc.xmlWriter import XMLWriter
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.DefaultTable import DefaultTable
from fontTools.ttLib.tables.otBase import OTLOffsetOverflowError, USE_HARFBUZZ_REPACKER

from fontbuild import compact_layout
from fontbuild import layout
from test_storage import fixture, serialized


def clock_font(count=96):
    font = fixture()
    names = [f'clock_{i}' for i in range(count+1)]
    order = font.getGlyphOrder().copy()
    for name in names:
        font['glyf'][name] = TTGlyphPen(None).glyph()
        font['hmtx'][name] = (300, 0)
    font.setGlyphOrder(order+names)
    for table in font['cmap'].tables:
        if table.isUnicode():
            table.cmap = {97: names[0], 98: names[count//3]}
    features = ['languagesystem DFLT dflt;']
    coverage = '['+' '.join(names)+']'
    for i in range(count):
        features += [f'lookup SET{i} {{ sub {names[i]} by {names[i+1]}; }} SET{i};',
                     f"lookup CLOCK{i} useExtension {{ sub {coverage}' lookup SET{i}; }} CLOCK{i};"]
    features.append('feature calt { '+' '.join(f'lookup CLOCK{i};' for i in range(count))+' } calt;')
    addOpenTypeFeaturesFromString(font, '\n'.join(features))
    font.cfg[USE_HARFBUZZ_REPACKER] = False
    return font


def xml(font):
    output = StringIO()
    font['GSUB'].toXML(XMLWriter(output), font)
    return output.getvalue()


@pytest.mark.parametrize('scope', [512, 1024, 60000])
def test_shared_extensions_preserve_logical_tables_and_every_clock_tick(scope, tmp_path):
    font = clock_font()
    before = serialized(font)
    original = TTFont(BytesIO(before))
    packed = layout._pack_extensions(font, 'GSUB', max_scope=scope)
    assert len(packed) < len(original.reader['GSUB'])
    table = DefaultTable('GSUB')
    table.data = packed
    font['GSUB'] = table
    after = serialized(font)
    assert len(after) < len(before)
    new = TTFont(BytesIO(after))
    assert xml(original) == xml(new)
    assert original.getGlyphOrder() == new.getGlyphOrder()
    for tag in ('glyf', 'loca', 'hmtx', 'cmap', 'name'):
        assert original.getTableData(tag) == new.getTableData(tag)
    if shaper := shutil.which('hb-shape'):
        for name, data in (('original', before), ('packed', after)):
            path = tmp_path/f'{name}.ttf'
            path.write_bytes(data)
            glyphs = json.loads(subprocess.check_output(
                [shaper, str(path), 'ababa', '--features=calt=1', '--output-format=json']))
            assert [glyph['g'] for glyph in glyphs] == ['clock_96']*5


def test_compact_layout_keeps_smaller_encoding_and_is_idempotent():
    font = clock_font()
    before = len(font.getTableData('GSUB'))
    saved = compact_layout(font)
    assert saved > 0
    assert len(font.getTableData('GSUB')) == before-saved
    assert compact_layout(font) == 0
    assert compact_layout(fixture()) == 0


def test_no_sharing_guard_retains_original_table():
    font = clock_font()
    for lookup in font['GSUB'].table.LookupList.Lookup:
        if lookup.LookupType == 7:
            lookup.SubTable[0].ExtSubTable.DontShare = True
            break
    original = font['GSUB']
    before = font.getTableData('GSUB')
    assert compact_layout(font) == 0
    assert font['GSUB'] is original
    assert font.getTableData('GSUB') == before


def test_offset_overflow_retains_the_existing_valid_encoding(monkeypatch):
    font = clock_font()
    before = font.getTableData('GSUB')
    original = font['GSUB']
    def overflow(*args, **kwargs):
        raise OTLOffsetOverflowError(None)
    monkeypatch.setattr(layout, '_pack_extensions', overflow)
    assert compact_layout(font) == 0
    assert font['GSUB'] is original
    assert font.getTableData('GSUB') == before


def test_excessive_reuse_retains_the_existing_shaper_work_budget(monkeypatch):
    font = clock_font()
    original = font['GSUB']
    before = font.getTableData('GSUB')
    # A candidate can satisfy Offset16 bounds while shrinking the encoded
    # table too far for a shaper's repeated-traversal work budget.
    monkeypatch.setattr(layout, '_pack_extensions', lambda *args: b'\0'*(len(before)//3))
    assert compact_layout(font) == 0
    assert font['GSUB'] is original
    assert font.getTableData('GSUB') == before
