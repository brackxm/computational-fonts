#!/usr/bin/env python3
# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Build a Markdown-style formatting font. Requires FontTools.

Flat emphasis, inline code, strikethrough and three heading sizes are computed
in GSUB. The underlying markup remains ordinary editable text.
"""

import argparse
from pathlib import Path
import re
import sys
import unicodedata

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "decoders"))
from shared.font_metadata import load_base_font, mark_modified_font, replace_font_names

SOURCE_DIR = ROOT / "decoders/shared/fonts/roboto-2"
SOURCES = {"regular": "Roboto-Regular.ttf", "bold": "Roboto-Bold.ttf",
           "italic": "Roboto-Italic.ttf", "both": "Roboto-BoldItalic.ttf"}
CHARS = "".join(chr(code) for code in range(32, 127)) + "".join(
    chr(code) for code in range(160, 256) if unicodedata.category(chr(code)).startswith("L"))
ESCAPES = "*~`#\\"
MARKERS = {"italic": "*", "bold": "**", "both": "***", "strike": "~~"}
HEADING_SCALES = {"h1": 1.5, "h2": 1.25, "h3": 1.1}


def glyph_name(role, key):
    return "md." + role + "." + ".".join(f"{ord(char):04X}" for char in key)


def build_font(output_path, family_name=None):
    fonts = {}
    try:
        for face, filename in SOURCES.items():
            fonts[face] = load_base_font(SOURCE_DIR / filename, output_path)
        font = fonts["regular"]
        cmap = font.getBestCmap()
        upm = font["head"].unitsPerEm
        for face, source in fonts.items():
            if source["head"].unitsPerEm != upm:
                raise ValueError(f"{face} source has a different units-per-em value")
            missing = [char for char in CHARS if ord(char) not in source.getBestCmap()]
            if missing:
                raise ValueError(f"{face} source is missing required characters: {''.join(missing)!r}")
        if len({cmap[ord(char)] for char in CHARS}) != len(CHARS):
            raise ValueError("Formatter input glyphs must be distinct")
        if any(name.startswith("md.") for name in font.getGlyphOrder()):
            raise ValueError("Base contains reserved md. glyph names")

        order = list(font.getGlyphOrder())
        glyph_sets = {face: source.getGlyphSet() for face, source in fonts.items()}
        recordings = {}

        def recording(face, char):
            key = face, char
            if key not in recordings:
                pen = DecomposingRecordingPen(glyph_sets[face])
                glyph_sets[face][fonts[face].getBestCmap()[ord(char)]].draw(pen)
                recordings[key] = pen
            return recordings[key]

        def add(name, glyph, advance):
            if name in font["glyf"]:
                raise ValueError(f"Generated glyph name collision: {name}")
            font["glyf"][name] = glyph
            glyph.recalcBounds(font["glyf"])
            font["hmtx"].metrics[name] = (round(advance), getattr(glyph, "xMin", 0))
            order.append(name)

        def plain(name, text):
            pen = TTGlyphPen(font["glyf"])
            offset = 0
            for char in text:
                original = cmap[ord(char)]
                pen.addComponent(original, (1, 0, 0, 1, offset, 0))
                offset += font["hmtx"].metrics[original][0]
            add(name, pen.glyph(), offset)

        def styled(name, text, style):
            face = style if style in ("bold", "italic", "both") else "bold" if style in HEADING_SCALES else "regular"
            scale = HEADING_SCALES.get(style, 1)
            source_cmap = fonts[face].getBestCmap()
            pen = TTGlyphPen(None)
            offset = 0
            for char in text:
                original = source_cmap[ord(char)]
                advance = fonts[face]["hmtx"].metrics[original][0] * scale
                x_scale = y_scale = scale
                x_offset = offset
                if style == "code":
                    # Regular outlines are centered in equal cells; wide glyphs
                    # are narrowed to fit, rather than overlapping neighbours.
                    advance = round(upm * 0.64)
                    source_glyph = fonts[face]["glyf"][original]
                    source_glyph.recalcBounds(fonts[face]["glyf"])
                    left = getattr(source_glyph, "xMin", 0)
                    width = getattr(source_glyph, "xMax", 0) - left
                    x_scale = min(0.9, advance * 0.86 / width) if width else 0.9
                    y_scale = 0.9
                    x_offset += (advance - width * x_scale) / 2 - left * x_scale
                recording(face, char).replay(TransformPen(pen, (x_scale, 0, 0, y_scale, x_offset, 0)))
                offset += advance
            if style == "strike":
                bottom, thickness = round(upm * 0.29), max(1, round(upm * 0.04))
                pen.moveTo((0, bottom))
                pen.lineTo((round(offset), bottom))
                pen.lineTo((round(offset), bottom + thickness))
                pen.lineTo((0, bottom + thickness))
                pen.closePath()
            add(name, pen.glyph(), offset)

        gap = "md.gap"
        add(gap, TTGlyphPen(None).glyph(), 0)
        raw_escapes, literals = {}, {}
        for char in ESCAPES:
            raw_escapes[char] = glyph_name("escape.raw", char)
            literals[char] = glyph_name("escape.literal", char)
            plain(raw_escapes[char], "\\" + char)
            plain(literals[char], char)
        for mode, marker in {"code": "`", **MARKERS}.items():
            plain("md.marker." + mode, marker)
            add("md.close." + mode, TTGlyphPen(None).glyph(), 0)
        for mode in HEADING_SCALES:
            add("md.start." + mode, TTGlyphPen(None).glyph(), 0)

        fea = ["languagesystem DFLT dflt;", "languagesystem latn dflt;"]
        feature_lookups = []

        def cls(name, glyphs):
            fea.append("@" + name + " = [" + " ".join(glyphs) + "];")
            return "@" + name

        def lookup(name, rules):
            fea.extend([f"lookup {name} {{", *rules, f"}} {name};"])
            feature_lookups.append(name)

        lookup("ESCAPE_PAIRS", [f"sub {cmap[92]} {cmap[ord(char)]} by {raw_escapes[char]};"
                                for char in ESCAPES])

        # Heading prefixes are recognized only at the start of a shaping run.
        # Their body is frozen before inline parsing: heading contents are flat.
        heading_items = [(cmap[ord(char)], char) for char in CHARS] + [
            (raw_escapes[char], char) for char in ESCAPES]
        heading_input = cls("HEADING_INPUT", [name for name, _ in heading_items])
        # A consumed prefix still precedes the body. Keep it in the guard so
        # later heading lookups cannot mistake the body's hashes for a prefix.
        guard = cls("START_GUARD", sorted(
            set(cmap.values()) | set(raw_escapes.values()) | {".notdef"} |
            {"md.start." + mode for mode in HEADING_SCALES}))
        for level in (3, 2, 1):
            sequence = [cmap[35]] * level + [cmap[32]]
            action = f"HEADING_PREFIX_{level}"
            # The helper must not also run at top level.
            fea.append(f"lookup {action} {{ sub {' '.join(sequence)} by md.start.h{level}; }} {action};")
            context = sequence[0] + "' " + " ".join(sequence[1:])
            lookup(f"HEADING_START_{level}", [f"ignore sub {guard} {context};",
                   f"sub {sequence[0]}' lookup {action} {' '.join(sequence[1:])};"])
        heading_outputs = {}
        for mode in HEADING_SCALES:
            names = []
            for index, (_, text) in enumerate(heading_items):
                name = f"md.out.{mode}.{index}"
                styled(name, text, mode)
                names.append(name)
            heading_outputs[mode] = cls("OUT_" + mode.upper(), names)
        lookup("HEADING_BODY", [rule for mode, outputs in heading_outputs.items() for rule in (
            f"sub md.start.{mode} {heading_input}' by {outputs};",
            f"sub {outputs} {heading_input}' by {outputs};")])

        def marker_run(name, char, count, output):
            glyph = cmap[ord(char)]
            signals = [glyph] * count
            context = signals[0] + "'" + (" " + " ".join(signals[1:]) if count > 1 else "")
            action = name + "_ACTION"
            fea.append(f"lookup {action} {{ sub {' '.join(signals)} by {output}; }} {action};")
            lookup(name, [f"ignore sub {glyph} {context};", f"ignore sub {context} {glyph};",
                         f"sub {signals[0]}' lookup {action}" + (" " + " ".join(signals[1:]) if count > 1 else "") + ";"])

        def spans(tag, modes, items):
            names = [name for name, _ in items]
            inputs = cls("INPUT_" + tag, names)
            first = cls("FIRST_" + tag, [name for name, text in items if not text.isspace()])
            candidates, outputs = {}, {}
            last_candidates, first_candidates = {}, {}
            for mode in modes:
                cand_names, out_names, last = [], [], []
                for index, (_, text) in enumerate(items):
                    candidate = f"md.cand.{mode}.{index}"
                    output = f"md.out.{mode}.{index}"
                    plain(candidate, text)
                    styled(output, text, mode)
                    cand_names.append(candidate)
                    out_names.append(output)
                    if not text.isspace():
                        last.append(candidate)
                candidates[mode] = cls("CAND_" + mode.upper(), cand_names)
                outputs[mode] = cls("OUT_" + mode.upper(), out_names)
                last_candidates[mode] = cls("LAST_" + mode.upper(), last)
                first_candidates[mode] = cls("FIRST_CAND_" + mode.upper(), [
                    name for name, (_, text) in zip(cand_names, items) if not text.isspace()])
            lookup("FORWARD_" + tag, [rule for mode in modes for rule in (
                f"sub {candidates[mode] if mode == 'code' else last_candidates[mode]} md.marker.{mode}' by md.close.{mode};",
                # Starting whitespace is not part of a span; closing whitespace
                # similarly leaves the delimiter literal, with code excepted.
                f"sub md.marker.{mode} {inputs if mode == 'code' else first}' by {candidates[mode] if mode == 'code' else first_candidates[mode]};",
                f"sub {candidates[mode]} {inputs}' by {candidates[mode]};")])
            lookup("BACKWARD_" + tag, [f"rsub {candidates[mode]}' [md.close.{mode} {outputs[mode]}] by {outputs[mode]};"
                                     for mode in modes])
            lookup("HIDE_" + tag, [f"sub md.marker.{mode}' {outputs[mode]} by {gap};" for mode in modes])
            lookup("RELEASE_" + tag, [f"sub {candidates[mode]} by {inputs};" for mode in modes])

        marker_run("CODE_MARKER", "`", 1, "md.marker.code")
        # Escapes keep both original characters inside code, but lose the
        # backslash outside it. Code outputs cannot be parsed as inline markup.
        code_items = [(cmap[ord(char)], char) for char in CHARS] + [
            (raw_escapes[char], "\\" + char) for char in ESCAPES]
        spans("CODE", ("code",), code_items)
        lookup("RESTORE_CODE_MARKER", [f"sub md.marker.code by {cmap[96]};"])
        lookup("ESCAPE_LITERALS", [f"sub {raw_escapes[char]} by {literals[char]};" for char in ESCAPES])
        marker_run("STAR_THREE", "*", 3, "md.marker.both")
        marker_run("STAR_TWO", "*", 2, "md.marker.bold")
        marker_run("STAR_ONE", "*", 1, "md.marker.italic")
        marker_run("TILDE_TWO", "~", 2, "md.marker.strike")
        inline_items = [(cmap[ord(char)], char) for char in CHARS] + [
            (literals[char], char) for char in ESCAPES]
        spans("INLINE", tuple(MARKERS), inline_items)

        font.setGlyphOrder(order)
        if "GSUB" in font:
            del font["GSUB"]
        addOpenTypeFeaturesFromString(font, "\n".join(fea + ["feature rlig {", *(
            f"lookup {name};" for name in feature_lookups), "} rlig;"]))
        # A single font cannot have separate line metrics per glyph. Reserve
        # room for the largest heading without clipping its outlines.
        painted = [font["glyf"][name] for name in order if name.startswith("md.out.")]
        ascent = max(font["hhea"].ascent, *(getattr(g, "yMax", 0) for g in painted))
        descent = min(font["hhea"].descent, *(getattr(g, "yMin", 0) for g in painted))
        font["hhea"].ascent, font["hhea"].descent = ascent, descent
        font["OS/2"].sTypoAscender, font["OS/2"].sTypoDescender = ascent, descent
        font["OS/2"].usWinAscent = max(font["OS/2"].usWinAscent, ascent)
        font["OS/2"].usWinDescent = max(font["OS/2"].usWinDescent, -descent)
        family = family_name or "Markdown Formatter"
        ps_name = re.sub(r"[^A-Za-z0-9-]+", "-", family).strip("-") or "MarkdownFormatter"
        replace_font_names(font, {1: family, 2: "Regular", 3: "MarkdownFormatter",
                                 4: family + " Regular", 6: (ps_name + "-Regular")[:50],
                                 16: family, 17: "Regular"})
        mark_modified_font(font, "markdown", kind="formatter")
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        font.save(output_path)
        print(f"Saved {output_path}: {len(order)} glyphs")
    finally:
        for source in fonts.values():
            source.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).resolve().with_name("markdown-font.ttf"))
    parser.add_argument("--name", help="Optional font family name")
    args = parser.parse_args()
    try:
        build_font(args.output, args.name)
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
