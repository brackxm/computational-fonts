# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Web compression preserves the complete transformed stream and auxiliaries."""
from io import BytesIO

from fontTools.ttLib.woff2 import WOFF2FlavorData, WOFF2Reader

from fontbuild import compact_woff2
from test_storage import fixture


def test_recompression_keeps_every_decoded_byte_and_never_grows(tmp_path):
    font = fixture()
    font.flavor = 'woff2'
    path = tmp_path/'test.woff2'
    font.save(path)
    before = path.read_bytes()
    old = WOFF2Reader(BytesIO(before))
    saved = compact_woff2(path)
    after = path.read_bytes()
    new = WOFF2Reader(BytesIO(after))
    assert len(before)-len(after) == saved >= 0
    assert old.transformBuffer.getvalue() == new.transformBuffer.getvalue()
    assert [e.toString() for e in old.tables.values()] == [e.toString() for e in new.tables.values()]
    assert compact_woff2(path) == 0
    assert path.read_bytes() == after


def test_auxiliary_metadata_and_private_data_are_retained_verbatim(tmp_path):
    font = fixture()
    font.flavor = 'woff2'
    font.flavorData = WOFF2FlavorData()
    font.flavorData.metaData = b'<metadata>Retain font licensing</metadata>'
    font.flavorData.privData = b'private font data'
    path = tmp_path/'metadata.woff2'
    font.save(path)
    original = path.read_bytes()
    assert compact_woff2(path) == 0
    assert path.read_bytes() == original
