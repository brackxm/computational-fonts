# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Proportional Roboto lettering, baked into self-contained game outlines.

Source fonts are the repository's pinned Apache-2.0 Roboto 2 files. Curves
are decomposed at build time, so game fonts need no installed or runtime font.
The size parameter retains the geometric helpers' five-unit cap-height scale.
"""
from functools import cache
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen, replayRecording
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

SOURCE = Path(__file__).resolve().parents[2]/'decoders/shared/fonts/roboto-2'
NAME_RECORDS = {
    'copyright': 'Copyright 2015 Google Inc. All Rights Reserved.\nCopyright 2026 Michael Brackx',
    'trademark': 'Roboto is a trademark of Google.',
    'description': 'Original game implementation and artwork by Michael Brackx. '
                   'Text uses decomposed, scaled Roboto 2 Regular and Bold outlines (v2.138), '
                   'modified for this computational font under Apache License 2.0.',
}


@cache
def _face(weight):
    if weight not in ('regular', 'bold'):
        raise ValueError('Unknown text weight: '+weight)
    with TTFont(SOURCE/f'Roboto-{weight.title()}.ttf') as font:
        glyphs, cmap, result = font.getGlyphSet(), font.getBestCmap(), {}
        for code in range(32, 127):
            name = cmap[code]
            recording = DecomposingRecordingPen(glyphs)
            glyphs[name].draw(recording)
            bounds = BoundsPen(None)
            recording.replay(bounds)
            result[chr(code)] = recording.value, font['hmtx'][name][0], bounds.bounds
        return font['OS/2'].sCapHeight, result


def centered_lettering(pen, text, center_x, y, size=9, *, weight='bold'):
    """Center actual ink, retaining proportional spacing and quadratic curves."""
    cap_height, glyphs = _face(weight)
    scale, cursor, run, bounds = 5*size/cap_height, 0, [], []
    for char in text:
        if char not in glyphs:
            raise ValueError('Unsupported label character: '+repr(char))
        recording, advance, box = glyphs[char]
        run.append((cursor, recording))
        if box is not None:
            bounds.extend((cursor+box[0], cursor+box[2]))
        cursor += advance
    if not bounds:
        return
    origin = center_x-(min(bounds)+max(bounds))*scale/2
    for offset, recording in run:
        replayRecording(recording, TransformPen(pen, (scale, 0, 0, scale, origin+offset*scale, y)))
