# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Recompress WOFF2 streams without reconstructing or changing font tables."""
from io import BytesIO
from pathlib import Path
import struct


def compact_woff2(path):
    """Keep a smaller standard Brotli stream with identical decoded bytes.

    Table directories, transforms, glyphs and layout data stay byte-identical.
    Fonts with ancillary metadata/private blocks retain their existing stream.
    Brotli is imported only for webfont builds that already require it.
    """
    import brotli
    from fontTools.ttLib.woff2 import WOFF2Reader

    path = Path(path)
    original = path.read_bytes()
    reader = WOFF2Reader(BytesIO(original))
    if reader.metaOffset or reader.privOffset:
        return 0
    directory_end = 48+sum(len(entry.toString()) for entry in reader.tables.values())
    decoded = reader.transformBuffer.getvalue()
    encoded = brotli.compress(decoded, mode=brotli.MODE_GENERIC)
    result = bytearray(original[:directory_end]+encoded)
    result += b'\0'*(-len(result) % 4)
    if len(result) >= len(original):
        return 0
    assert brotli.decompress(encoded) == decoded
    struct.pack_into('>I', result, 8, len(result))
    struct.pack_into('>I', result, 20, len(encoded))
    path.write_bytes(result)
    return len(original)-len(result)
