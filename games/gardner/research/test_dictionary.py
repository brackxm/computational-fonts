# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Verify dictionary IDs and every route class through real HarfBuzz."""
from array import array
import struct
import sys

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.DefaultTable import DefaultTable
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable
import uharfbuzz as hb


def check_dictionary(path, tree_path, stem, directory):
    manifest = stem.with_suffix('.dispatch.bin').read_bytes()
    magic, width, low, high, dispatch, leaf, banks, lookup = struct.unpack_from('<8I', manifest)
    assert magic == 0x47504432 and len(manifest) == 56 + 20*banks
    with TTFont(path, lazy=True) as font:
        raw = bytearray(font.getTableData('GSUB'))
        gdef, order = font.getTableData('GDEF'), font.getGlyphOrder()

        def u16(at):
            return struct.unpack_from('>H', raw, at)[0]

        def u32(at):
            return struct.unpack_from('>I', raw, at)[0]

        def coverage(at):
            fmt, count = u16(at), u16(at + 2)
            if fmt == 1:
                return struct.unpack_from('>' + str(count) + 'H', raw, at + 4)
            assert fmt == 2
            glyphs = []
            for i in range(count):
                first, last, index = struct.unpack_from('>3H', raw, at + 4 + 6*i)
                assert index == len(glyphs)
                glyphs.extend(range(first, last + 1))
            return glyphs

        lookup_list = u16(8)

        def subtables(index):
            at = lookup_list + u16(lookup_list + 2 + 2*index)
            outer, flags, count = u16(at), u16(at + 2), u16(at + 4)
            assert flags == 0
            for i in range(count):
                sub, kind = at + u16(at + 6 + 2*i), outer
                if outer == 7:
                    kind = u16(sub + 2)
                    sub += u32(sub + 4)
                yield kind, sub

        def singles(index):
            for kind, sub in subtables(index):
                assert kind == 1 and u16(sub) == 2
                count = u16(sub + 4)
                sources = coverage(sub + u16(sub + 2))
                assert len(sources) == count
                targets = struct.unpack_from('>' + str(count) + 'H', raw, sub + 6)
                yield from zip(sources, targets)

        aliases, route_samples = {}, {}
        for bank in range(banks):
            _, _, pair, *routes = struct.unpack_from('<5i', manifest, 56 + 20*bank)
            if pair >= 0:
                for source, alias in singles(pair):
                    aliases.setdefault(alias, bank*width + source - low)
            # Sample each actual low-glyph class in each bit's route table.
            # This covers shared-leaf actions even when no dictionary ID uses them.
            for bit, route in enumerate(routes):
                for kind, sub in subtables(route):
                    assert kind == 5 and u16(sub) == 2
                    assert tuple(coverage(sub + u16(sub + 2))) == (dispatch + 2*bank + bit,)
                    classes = sub + u16(sub + 4)
                    assert u16(classes) == 2
                    for i in range(u16(classes + 2)):
                        first, last, value = struct.unpack_from('>3H', raw, classes + 4 + 6*i)
                        first, last = max(first, low), min(last, low + width - 1)
                        if first <= last:
                            route_samples.setdefault((bank, bit, value), bank*width + first - low)
        # Global IDs are dense from zero and can overlap base/GDEF mark glyphs.
        assert aliases and set(aliases) == set(range(len(aliases)))
        assert max(aliases) < len(order)
        feature_list = u16(6)
        assert raw[feature_list + 2:feature_list + 6] == b'liga'
        feature = feature_list + u16(feature_list + 6)
        # Only the top-level feature list changes: invoke the real dispatcher
        # directly, with no game setup. Nested lookups and GDEF stay untouched.
        struct.pack_into('>HH', raw, feature + 2, 1, lookup)
        font['GSUB'] = DefaultTable('GSUB')
        font['GSUB'].data = bytes(raw)
        cmap = CmapSubtable.newSubtable(12)
        cmap.platformID, cmap.platEncID, cmap.language = 0, 4, 0
        cmap.cmap = {0x100000+i: name for i, name in enumerate(order)}
        font['cmap'].tables.append(cmap)
        output = directory / 'dictionary.ttf'
        font.save(output)
    with TTFont(output, lazy=True) as font:
        assert font.getTableData('GSUB') == raw
        assert font.getTableData('GDEF') == gdef
    addresses = array('I')
    addresses.frombytes(stem.with_suffix('.addresses').read_bytes())
    # Compiler metadata uses little-endian words, independently of this host.
    if sys.byteorder != 'little':
        addresses.byteswap()
    assert route_samples
    needed = set(aliases.values()) | set(route_samples.values())
    nodes = {address: i for i, address in enumerate(addresses) if address in needed}
    assert len(nodes) == len(needed)
    tree = tree_path.read_bytes()
    offset = 80 + 4*struct.unpack_from('<I', tree, 12)[0]
    font, checks = hb.Font(hb.Face(output.read_bytes())), 0

    def check(address, bit):
        node, (bank, slot) = nodes[address], divmod(address, width)
        values = [dispatch + 2*bank + bit, low + slot, low + slot]
        buffer = hb.Buffer()
        buffer.add_str(''.join(chr(0x100000+v) for v in values))
        buffer.direction, buffer.script = 'ltr', 'Latn'
        hb.shape(font, buffer, {'liga': True})
        actual = [g.codepoint for g in buffer.glyph_infos]
        child = struct.unpack_from('<i', tree, offset + 12*node + 4 + 4*bit)[0]
        if child < 0:
            expected = [leaf - 1 - child]
        else:
            target = addresses[child]
            expected = [high + target//width, low + target % width]
        assert actual == expected, (address, bit, actual, expected)

    for address in aliases.values():
        for bit in [0, 1]:
            check(address, bit)
            checks += 1
    for (_, bit, _), address in route_samples.items():
        check(address, bit)
    return dict(status='pass', temporary_dictionary_glyphs=len(aliases), checks=checks,
                route_class_checks=len(route_samples),
                includes_notdef=0 in aliases,
                scope='Actual HarfBuzz dispatcher, both bits for every temporary dictionary glyph '
                      'and one representative per bank/bit route class; '
                      'test-only cmap and top-level feature; nested GSUB and GDEF unchanged.')
