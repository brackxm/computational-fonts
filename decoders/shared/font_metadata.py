# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Retained third-party notices: see THIRD_PARTY_NOTICES.md at the project root.

"""Decoder base validation and derivative attribution metadata."""

import hashlib
from io import BytesIO
from pathlib import Path
import re
import struct

from fontTools.ttLib import TTFont, TTLibError

DEFAULT_BASE = Path(__file__).resolve().parent / "fonts" / "roboto-2" / "Roboto-Regular.ttf"
MODIFICATION_COPYRIGHT = "Copyright 2026 Michael Brackx. Decoder modifications."


def load_base_font(base_path, output_path):
    """Load a usable base without allowing its source file to be overwritten."""
    base, output = Path(base_path), Path(output_path)
    if base.resolve() == output.resolve() or (output.exists() and base.samefile(output)):
        raise ValueError("Output must differ from the base font path")
    # Read once so the outlines and identity use the same bytes. An in-memory
    # reader also avoids holding the source file open if a later build fails.
    data = base.read_bytes()
    font = None
    try:
        font = TTFont(BytesIO(data))
        if any(table not in font for table in ("glyf", "hmtx", "name")):
            raise ValueError("Base must be a TrueType font with glyf, hmtx, and name tables")
        if "cmap" not in font or not font.getBestCmap():
            raise ValueError("Base font has no usable Unicode cmap")
        # FontTools loads tables lazily; validate the required tables while
        # malformed-font errors can still be reported as input errors.
        for tag in ("glyf", "hmtx", "name"):
            font[tag]
    except (TTLibError, struct.error, AssertionError, KeyError) as exc:
        if font is not None:
            font.close()
        raise ValueError(f"Cannot read base font {base}: {exc}") from exc
    except (ValueError, OSError):
        if font is not None:
            font.close()
        raise
    font._decoder_base_digest = hashlib.sha256(data).digest()
    return font


def validate_marker(marker, reserved, option):
    """Keep a start/delimiter marker distinct from characters it must parse."""
    if len(marker) != 1 or marker.isspace() or marker in reserved:
        raise ValueError(f"{option} must be one non-whitespace character outside {reserved!r}")


def validate_marker_glyph(cmap, marker, reserved, option):
    """Different characters must not alias the same parsing glyph in a base."""
    glyph = cmap.get(ord(marker))
    if glyph is not None and any(cmap.get(ord(ch)) == glyph for ch in reserved):
        raise ValueError(f"{option} glyph must be distinct from input glyphs in the base font")


def _append_notice(font, name_id, notice):
    table = font["name"]
    records = [record for record in table.names if record.nameID == name_id]
    for record in records:
        existing = record.toUnicode()
        if notice not in existing:
            record.string = (existing.rstrip() + "\n" + notice).lstrip().encode(
                record.getEncoding(), errors="replace")
    if not any(record.platformID == 3 and record.platEncID == 1 and record.langID == 0x409
               for record in records):
        existing = records[0].toUnicode() if records else notice
        table.setName(existing, name_id, 3, 1, 0x409)


def replace_font_names(font, replacements):
    """Rename every locale and supply the common Windows/Macintosh records."""
    table = font["name"]
    for record in table.names:
        if record.nameID in replacements:
            record.string = replacements[record.nameID].encode(
                record.getEncoding(), errors="replace")
    for name_id, value in replacements.items():
        table.setName(value, name_id, 3, 1, 0x409)
        table.setName(value, name_id, 1, 0, 0)


def mark_modified_font(font, decoder):
    """Keep the base's copyright/license and identify our changes explicitly."""
    _append_notice(font, 0, MODIFICATION_COPYRIGHT)
    _append_notice(font, 10, f"Modified by Michael Brackx (2026) for computational-fonts: "
                   f"{decoder} decoder glyphs and OpenType substitution rules added. "
                   "The base font's license and attribution are retained.")
    # Family names stay readable; unique and PostScript names distinguish
    # settings (including plugboard/wheel settings) and different base fonts.
    digest = hashlib.sha256(font._decoder_base_digest)
    for tag in ("GSUB", "glyf", "hmtx"):
        digest.update(font[tag].compile(font))
    identity = digest.hexdigest()[:12]
    for name_id in (3, 6):
        if font["name"].getName(name_id, 3, 1, 0x409) is None:
            existing = font["name"].getDebugName(name_id) or decoder
            font["name"].setName(existing, name_id, 3, 1, 0x409)
    for record in font["name"].names:
        if record.nameID not in (3, 6):
            continue
        existing = re.sub(r"[;-][a-f0-9]{12}$", "", record.toUnicode())
        value = (existing[:50] + "-" + identity if record.nameID == 6
                 else existing + ";" + identity)
        record.string = value.encode(record.getEncoding(), errors="replace")
    if "DSIG" in font:
        del font["DSIG"]
