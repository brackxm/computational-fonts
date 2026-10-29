# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Storage reductions preserve outlines, public IDs, metrics and instructions."""
from io import BytesIO

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables.ttProgram import Program
from fontTools.ttLib.tables._g_l_y_f import USE_MY_METRICS, flagOverlapSimple

from fontbuild import compact_glyphs


def rectangle(x):
    pen = TTGlyphPen(None)
    pen.moveTo((x, 0))
    pen.lineTo((x+20, 0))
    pen.lineTo((x+20, 20))
    pen.lineTo((x, 20))
    pen.closePath()
    return pen.glyph()


def fixture(state_count=40):
    glyphs = {'.notdef': TTGlyphPen(None).glyph(), 'a': rectangle(0),
              'b': rectangle(40), 'duplicate': rectangle(0), 'hinted': rectangle(0)}
    program = Program()
    program.fromBytecode(b'\x00')
    glyphs['hinted'].program = program
    for i in range(state_count):
        name = f'c{i}'
        glyphs[name] = rectangle(100+i)
        pen = TTGlyphPen(glyphs)
        for part in ('a', 'b', name):
            pen.addComponent(part, (1, 0, 0, 1, 0, 0))
        glyphs[f'state{i}'] = pen.glyph()
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder(list(glyphs))
    builder.setupCharacterMap({32+i: name for i, name in enumerate(glyphs)})
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics({name: (300+i, getattr(glyph, 'xMin', 0))
                                    for i, (name, glyph) in enumerate(glyphs.items())})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    builder.setupNameTable({'familyName': 'Storage test', 'styleName': 'Regular'})
    builder.setupPost()
    builder.setupMaxp()
    builder.font.recalcTimestamp = False
    return builder.font


def serialized(font):
    output = BytesIO()
    font.save(output)
    return output.getvalue()


def test_smaller_storage_keeps_all_original_outlines_metrics_and_character_mappings():
    font = fixture()
    before = serialized(font)
    old = TTFont(BytesIO(before))
    changes = compact_glyphs(font)
    after = serialized(font)
    assert changes['aliases'] == 1
    assert changes['pairs'] >= 1
    assert len(after) < len(before)
    new = TTFont(BytesIO(after))
    order = old.getGlyphOrder()
    assert new.getGlyphOrder()[:len(order)] == order
    assert new.getBestCmap() == old.getBestCmap()
    for name in order:
        assert new['hmtx'][name] == old['hmtx'][name]
        assert new['glyf'][name].getCoordinates(new['glyf']) == old['glyf'][name].getCoordinates(old['glyf'])
    assert new['glyf']['hinted'].program.getBytecode() == b'\x00'
    assert not new['glyf']['hinted'].isComposite()
    assert all(new['hmtx'][name][0] == 0 for name in new.getGlyphOrder()[len(order):])


def test_variable_fonts_are_left_intact():
    font = fixture()
    font['fvar'] = newTable('fvar')
    before = font.getGlyphOrder().copy()
    assert compact_glyphs(font) == {'aliases': 0, 'pairs': 0}
    assert font.getGlyphOrder() == before
    assert not font['glyf']['duplicate'].isComposite()


def test_translated_components_do_not_participate_in_pair_sharing():
    font = fixture()
    for name in font.getGlyphOrder():
        glyph = font['glyf'][name]
        if glyph.isComposite():
            glyph.components[0].x = 17
    assert compact_glyphs(font)['pairs'] == 0


def test_positioned_pairs_keep_their_exact_offsets_and_contour_order():
    font = fixture()
    for name in font.getGlyphOrder():
        glyph = font['glyf'][name]
        if glyph.isComposite():
            glyph.components[0].x, glyph.components[0].y = -137, 241
            glyph.components[1].x, glyph.components[1].y = 319, -57
    before = serialized(font)
    old = TTFont(BytesIO(before))
    assert compact_glyphs(font, positioned=True)['pairs'] > 0
    after = serialized(font)
    assert len(after) < len(before)
    new = TTFont(BytesIO(after))
    order = old.getGlyphOrder()
    assert new.getGlyphOrder()[:len(order)] == order
    assert new.getBestCmap() == old.getBestCmap()
    for name in order:
        assert new['hmtx'][name] == old['hmtx'][name]
        assert new['glyf'][name].getCoordinates(new['glyf']) == old['glyf'][name].getCoordinates(old['glyf'])


def test_cached_metric_tables_prevent_appending_unaccounted_glyphs():
    font = fixture()
    font['LTSH'] = newTable('LTSH')
    order = font.getGlyphOrder().copy()
    changes = compact_glyphs(font)
    assert changes == {'aliases': 1, 'pairs': 0}
    assert font.getGlyphOrder() == order


def test_metric_delegation_and_overlap_flags_keep_their_original_glyph_level():
    font = fixture()
    for i in range(2):
        pen = TTGlyphPen(font['glyf'])
        pen.addComponent('a', (1, 0, 0, 1, 0, 0))
        glyph = pen.glyph()
        glyph.components[0].flags |= USE_MY_METRICS
        font['glyf'][f'metrics{i}'] = glyph
        font['hmtx'][f'metrics{i}'] = (300, 0)
        glyph = rectangle(0)
        glyph.flags[0] |= flagOverlapSimple
        font['glyf'][f'overlap{i}'] = glyph
        font['hmtx'][f'overlap{i}'] = (300, 0)
    compact_glyphs(font)
    for i in range(2):
        assert font['glyf'][f'metrics{i}'].components[0].flags & USE_MY_METRICS
        assert not font['glyf'][f'overlap{i}'].isComposite()
        assert font['glyf'][f'overlap{i}'].flags[0] & flagOverlapSimple


def contour_fixture():
    font = fixture()
    for i in range(42):
        pen = TTGlyphPen(None)
        for x, y in ((-137, 241), (319, -57)):
            for _ in range(5):
                x += 120
                pen.moveTo((x+40, y))
                pen.qCurveTo((x+40, y+40), (x, y+40))
                pen.qCurveTo((x-40, y+40), (x-40, y))
                pen.qCurveTo((x-40, y-40), (x, y-40))
                pen.qCurveTo((x+40, y-40), (x+40, y))
                pen.closePath()
            # Unique intervening contours must retain their point order too.
            pen.moveTo((800+i, y))
            pen.lineTo((820+i, y))
            pen.lineTo((820+i, y+20))
            pen.lineTo((800+i, y+20))
            pen.closePath()
        name = f'scene{i}'
        glyph = pen.glyph()
        glyph.recalcBounds(font['glyf'])
        font['glyf'][name] = glyph
        font['hmtx'][name] = (1600+i, glyph.xMin)
        if i == 40:
            glyph.program = Program()
            glyph.program.fromBytecode(b'\x00')
        if i == 41:
            glyph.flags[0] |= flagOverlapSimple
    return font


def test_contour_runs_keep_curves_winding_positions_and_all_original_glyph_ids():
    from fontbuild import compact_contours
    font = contour_fixture()
    before = serialized(font)
    old = TTFont(BytesIO(before))
    changes = compact_contours(font)
    assert changes['glyphs'] == 40
    assert changes['helpers'] > 0
    after = serialized(font)
    assert len(after) < len(before)
    new = TTFont(BytesIO(after))
    order = old.getGlyphOrder()
    assert new.getGlyphOrder()[:len(order)] == order
    assert new.getBestCmap() == old.getBestCmap()
    for name in order:
        assert new['hmtx'][name] == old['hmtx'][name]
        assert new['glyf'][name].getCoordinates(new['glyf']) == old['glyf'][name].getCoordinates(old['glyf'])
    assert not new['glyf']['scene40'].isComposite()
    assert new['glyf']['scene40'].program.getBytecode() == b'\x00'
    assert new['glyf']['scene41'].flags[0] & flagOverlapSimple
    assert all(new['hmtx'][name][0] == 0 for name in new.getGlyphOrder()[len(order):])


def test_contour_sharing_respects_auxiliary_caches_and_no_saving_cases():
    from fontbuild import compact_contours
    font = fixture()
    order = font.getGlyphOrder().copy()
    assert compact_contours(font) == {'glyphs': 0, 'helpers': 0}
    assert font.getGlyphOrder() == order
    for tag in ('fvar', 'LTSH', 'hdmx'):
        font = contour_fixture()
        font[tag] = newTable(tag)
        order = font.getGlyphOrder().copy()
        assert compact_contours(font) == {'glyphs': 0, 'helpers': 0}
        assert font.getGlyphOrder() == order
        assert not font['glyf']['scene0'].isComposite()


def test_refining_contour_helpers_preserves_the_checkpoint_and_original_glyphs():
    from fontbuild import compact_contours
    font = contour_fixture()
    compact_contours(font)
    old = TTFont(BytesIO(serialized(font)))
    compact_contours(font, rounds=8, min_uses=4)
    new = TTFont(BytesIO(serialized(font)))
    order = old.getGlyphOrder()
    assert new.getGlyphOrder()[:len(order)] == order
    for name in order:
        assert old['hmtx'][name] == new['hmtx'][name]
        assert old['glyf'][name].getCoordinates(old['glyf']) == new['glyf'][name].getCoordinates(new['glyf'])
    assert new['glyf']['scene40'].program.getBytecode() == b'\x00'
    assert new['glyf']['scene41'].flags[0] & flagOverlapSimple


def test_two_uses_can_share_long_runs_without_changing_either_glyph():
    from fontbuild import compact_contours
    font = fixture()
    original_order = font.getGlyphOrder().copy()
    names = []
    for index in range(2):
        pen = TTGlyphPen(None)
        for i in range(24):
            x = i*40
            pen.moveTo((x, 0))
            pen.lineTo((x+20, 0))
            pen.lineTo((x+20, 20))
            pen.lineTo((x, 20))
            pen.closePath()
        pen.moveTo((index, 40))
        pen.lineTo((index+20, 40))
        pen.lineTo((index+20, 60))
        pen.closePath()
        name = f'rare{index}'
        font['glyf'][name] = pen.glyph()
        font['hmtx'][name] = (1100+index, 0)
        names.append(name)
    font.setGlyphOrder(original_order+names)
    font['glyf'].setGlyphOrder(font.getGlyphOrder())
    before = serialized(font)
    old = TTFont(BytesIO(before))
    assert compact_contours(font)['helpers'] == 0
    assert compact_contours(font, rounds=8, min_uses=2)['helpers'] > 0
    after = serialized(font)
    assert len(after) < len(before)
    new = TTFont(BytesIO(after))
    order = old.getGlyphOrder()
    assert new.getGlyphOrder()[:len(order)] == order
    for name in order:
        assert new['hmtx'][name] == old['hmtx'][name]
        assert new['glyf'][name].getCoordinates(new['glyf']) == old['glyf'][name].getCoordinates(old['glyf'])


def test_eight_use_pairs_pay_for_their_helper_and_keep_the_original_glyphs():
    font = fixture(8)
    assert compact_glyphs(font)['pairs'] == 0
    before = serialized(font)
    old = TTFont(BytesIO(before))
    assert compact_glyphs(font, min_uses=8)['pairs'] > 0
    after = serialized(font)
    assert len(after) < len(before)
    new = TTFont(BytesIO(after))
    order = old.getGlyphOrder()
    assert new.getGlyphOrder()[:len(order)] == order
    for name in order:
        assert new['hmtx'][name] == old['hmtx'][name]
        assert new['glyf'][name].getCoordinates(new['glyf']) == old['glyf'][name].getCoordinates(old['glyf'])


def test_eight_use_pairs_retain_the_existing_encoding_when_helper_names_are_costly():
    font = fixture(8)
    order = font.getGlyphOrder().copy()
    for depth in range(1, 41):
        name = '_'*depth+'share0'
        font['glyf'][name] = TTGlyphPen(None).glyph()
        font['hmtx'][name] = (0, 0)
        order.append(name)
    font.setGlyphOrder(order)
    font['glyf'].setGlyphOrder(order)
    assert compact_glyphs(font, min_uses=8)['pairs'] == 0
    assert font.getGlyphOrder() == order
