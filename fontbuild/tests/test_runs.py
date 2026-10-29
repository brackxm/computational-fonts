# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Ordered component runs retain public geometry and bounded helper depth."""
from io import BytesIO

import pytest
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables._g_l_y_f import USE_MY_METRICS, OVERLAP_COMPOUND
from fontTools.ttLib.tables.ttProgram import Program

from fontbuild import compact_runs
from test_storage import fixture, serialized


def scenes(*, count=12, positioned=False):
    font = fixture(count)
    for i in range(count):
        pen = TTGlyphPen(font['glyf'])
        for j, child in enumerate(['a', 'b']*4+[f'c{i}']):
            x, y = ((450+j*91, -137) if positioned else (0, 0))
            pen.addComponent(child, (1, 0, 0, 1, x, y))
        font['glyf'][f'state{i}'] = pen.glyph()
    return font


@pytest.mark.parametrize('positioned', [False, True])
def test_shared_runs_preserve_all_existing_ids_points_flags_metrics_and_hints(positioned):
    font = scenes(positioned=positioned)
    before = serialized(font)
    old = TTFont(BytesIO(before))
    changes = compact_runs(font, positioned=positioned)
    assert changes['helpers'] > 0
    assert changes['uses'] >= 12
    after = serialized(font)
    assert len(after) < len(before)
    new = TTFont(BytesIO(after))
    order = old.getGlyphOrder()
    assert new.getGlyphOrder()[:len(order)] == order
    for name in order:
        assert new['hmtx'][name] == old['hmtx'][name]
        assert new['glyf'][name].getCoordinates(new['glyf']) == old['glyf'][name].getCoordinates(old['glyf'])
    assert new['glyf']['hinted'].program.getBytecode() == b'\x00'
    assert new['maxp'].maxComponentDepth <= 16
    assert all(new['hmtx'][name][0] == 0 for name in new.getGlyphOrder()[len(order):])


def test_referenced_composites_hints_metric_delegation_overlap_and_transforms_stay_intact():
    font = scenes()
    pen = TTGlyphPen(font['glyf'])
    pen.addComponent('state0', (1, 0, 0, 1, 0, 0))
    font['glyf']['envelope'] = pen.glyph()
    font['hmtx']['envelope'] = (300, 0)
    font['glyf']['state1'].program = Program()
    font['glyf']['state1'].program.fromBytecode(b'\x00')
    font['glyf']['state2'].components[0].flags |= USE_MY_METRICS
    font['glyf']['state3'].components[0].flags |= OVERLAP_COMPOUND
    font['glyf']['state4'].components[0].transform = ((0.5, 0), (0, 0.5))
    old = TTFont(BytesIO(serialized(font)))
    assert compact_runs(font)['helpers'] > 0
    new = TTFont(BytesIO(serialized(font)))
    for name in ('state0', 'state1', 'state2', 'state3', 'state4', 'envelope'):
        assert old['glyf'][name].compile(old['glyf']) == new['glyf'][name].compile(new['glyf'])


@pytest.mark.parametrize('tag', ['fvar', 'gvar', 'HVAR', 'hdmx', 'LTSH', 'vmtx'])
def test_variable_fonts_and_per_glyph_caches_do_not_gain_helpers(tag):
    font = scenes()
    order = font.getGlyphOrder().copy()
    font[tag] = newTable(tag)
    assert compact_runs(font) == {'helpers': 0, 'uses': 0}
    assert font.getGlyphOrder() == order


def test_positioned_components_require_explicit_opt_in_and_runs_must_pay_for_themselves():
    font = scenes(positioned=True)
    assert compact_runs(font) == {'helpers': 0, 'uses': 0}
    font = scenes(count=1)
    assert compact_runs(font) == {'helpers': 0, 'uses': 0}
    with pytest.raises(ValueError):
        compact_runs(font, lengths=(2,))


def test_runs_cannot_exceed_the_sixteen_level_component_depth_bound():
    font = scenes()
    for i in range(15):
        pen = TTGlyphPen(font['glyf'])
        pen.addComponent('a' if i == 0 else f'chain{i-1}', (1, 0, 0, 1, 0, 0))
        font['glyf'][f'chain{i}'] = pen.glyph()
        font['hmtx'][f'chain{i}'] = (0, 0)
    for i in range(12):
        pen = TTGlyphPen(font['glyf'])
        for _ in range(8):
            pen.addComponent('chain14', (1, 0, 0, 1, 0, 0))
        font['glyf'][f'state{i}'] = pen.glyph()
    assert compact_runs(font) == {'helpers': 0, 'uses': 0}
    assert TTFont(BytesIO(serialized(font)))['maxp'].maxComponentDepth == 16


def test_full_glyph_budget_retains_existing_artwork_without_appending_helpers():
    font = scenes()
    for i in range(65534-len(font.getGlyphOrder())):
        name = f'empty{i}'
        font['glyf'][name] = TTGlyphPen(None).glyph()
        font['hmtx'][name] = (0, 0)
    font['post'].formatType = 3.0
    order = font.getGlyphOrder().copy()
    before = font['glyf']['state0'].compile(font['glyf'])
    assert len(order) == 65534
    assert compact_runs(font) == {'helpers': 0, 'uses': 0}
    assert font.getGlyphOrder() == order
    assert font['glyf']['state0'].compile(font['glyf']) == before
