# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Original Game Sans outlines: a small alphabet for computational game labels.

The coordinates below are independently drawn stroke skeletons, not traced or
imported font data. A quadratic stroker gives both weights the same advances.
Building the base requires FontTools and skia-pathops; using it only requires
FontTools. Importing this module does not read or write files.
"""
from functools import cache
from math import atan2, cos, hypot, pi, sin
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen, RecordingPen, replayRecording
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

FAMILY = 'Game Sans'
CAP_HEIGHT = 700
COPYRIGHT = 'Copyright 2026 Michael Brackx'
DESCRIPTION = ('Original Game Sans lettering by Michael Brackx. Independently '
               'drawn geometric outlines; no third-party font outlines. Apache License 2.0.')
WEIGHTS = {'regular': 70, 'bold': 105}
FONT_DIR = Path(__file__).resolve().parent/'fonts'/'game-sans'


def path(*points):
    """A stroke starts at a point; later points are lines or (cx, cy, x, y) curves."""
    return points


def oval(width, height=700, bottom=0):
    half, middle = width/2, bottom+height/2
    return path((width, middle), (width, bottom+height, half, bottom+height),
                (0, bottom+height, 0, middle), (0, bottom, half, bottom),
                (width, bottom, width, middle))


# Widths describe the stroke skeleton; sidebearings and caps are added below.
# Curves intentionally share a small, rounded vocabulary, with open counters.
GLYPHS = {
    'A': (440, path((0, 0), (220, 700), (440, 0)), path((85, 260), (355, 260))),
    'B': (420, path((0, 0), (0, 700), (220, 700), (405, 700, 405, 535),
                    (405, 370, 220, 370), (0, 370)),
               path((220, 370), (420, 370, 420, 185), (420, 0, 220, 0), (0, 0))),
    'C': (440, path((430, 610), (340, 710, 225, 700), (0, 700, 0, 350),
                    (0, 0, 225, 0), (340, -10, 430, 90))),
    'D': (440, path((0, 0), (0, 700), (180, 700), (440, 700, 440, 350),
                    (440, 0, 180, 0), (0, 0))),
    'E': (380, path((380, 700), (0, 700), (0, 0), (380, 0)), path((0, 365), (310, 365))),
    'F': (380, path((0, 0), (0, 700), (380, 700)), path((0, 365), (310, 365))),
    'G': (460, path((440, 610), (350, 710, 235, 700), (0, 700, 0, 350),
                    (0, 0, 235, 0), (460, 0, 460, 220), (460, 325), (265, 325))),
    'H': (440, path((0, 0), (0, 700)), path((440, 0), (440, 700)), path((0, 350), (440, 350))),
    'I': (200, path((0, 700), (200, 700)), path((100, 700), (100, 0)), path((0, 0), (200, 0))),
    'J': (340, path((340, 700), (340, 175), (340, 0, 170, 0), (0, 0, 0, 140))),
    'K': (440, path((0, 0), (0, 700)), path((430, 700), (0, 300)), path((165, 450), (440, 0))),
    'L': (360, path((0, 700), (0, 0), (360, 0))),
    'M': (560, path((0, 0), (0, 700), (280, 240), (560, 700), (560, 0))),
    'N': (460, path((0, 0), (0, 700), (460, 0), (460, 700))),
    'O': (460, oval(460)),
    'P': (410, path((0, 0), (0, 700), (215, 700), (410, 700, 410, 510),
                    (410, 320, 215, 320), (0, 320))),
    'Q': (460, oval(460), path((280, 175), (485, -65))),
    'R': (430, path((0, 0), (0, 700), (215, 700), (410, 700, 410, 510),
                    (410, 320, 215, 320), (0, 320)), path((220, 320), (430, 0))),
    'S': (420, path((410, 610), (330, 700, 210, 700), (0, 700, 0, 525),
                    (0, 395, 210, 345), (420, 295, 420, 160),
                    (420, 0, 205, 0), (80, 0, 0, 90))),
    'T': (440, path((0, 700), (440, 700)), path((220, 700), (220, 0))),
    'U': (440, path((0, 700), (0, 220), (0, 0, 220, 0), (440, 0, 440, 220), (440, 700))),
    'V': (440, path((0, 700), (220, 0), (440, 700))),
    'W': (660, path((0, 700), (140, 0), (330, 480), (520, 0), (660, 700))),
    'X': (440, path((0, 700), (440, 0)), path((0, 0), (440, 700))),
    'Y': (440, path((0, 700), (220, 350), (440, 700)), path((220, 350), (220, 0))),
    'Z': (420, path((0, 700), (420, 700), (0, 0), (420, 0))),
    'a': (350, oval(350, 490), path((350, 490), (350, 0))),
    'b': (350, path((0, 700), (0, 0)), oval(350, 490)),
    'c': (330, path((325, 435), (265, 490, 175, 490), (0, 490, 0, 245),
                    (0, 0, 175, 0), (265, 0, 325, 55))),
    'd': (350, oval(350, 490), path((350, 700), (350, 0))),
    'e': (350, path((0, 250), (350, 250), (350, 490, 175, 490),
                    (0, 490, 0, 245), (0, 0, 180, 0), (275, 0, 335, 60))),
    'f': (240, path((80, 0), (80, 535), (80, 715, 240, 700)), path((0, 470), (240, 470))),
    'g': (350, oval(350, 490), path((350, 490), (350, -50), (350, -200, 175, -200),
                                 (65, -200, 15, -145))),
    'h': (350, path((0, 0), (0, 700)), path((0, 310), (0, 490, 180, 490),
                                        (350, 490, 350, 320), (350, 0))),
    'i': (0, path((0, 0), (0, 490)), path((0, 670), (0, 675))),
    'j': (130, path((130, 490), (130, -55), (130, -200, 0, -200)), path((130, 670), (130, 675))),
    'k': (340, path((0, 0), (0, 700)), path((330, 490), (0, 185)), path((135, 310), (340, 0))),
    'l': (95, path((0, 700), (0, 100), (0, 0, 95, 0))),
    'm': (590, path((0, 0), (0, 490)), path((0, 325), (0, 490, 145, 490),
                   (295, 490, 295, 325), (295, 0)),
               path((295, 325), (295, 490, 445, 490), (590, 490, 590, 325), (590, 0))),
    'n': (350, path((0, 0), (0, 490)), path((0, 310), (0, 490, 180, 490),
                                         (350, 490, 350, 320), (350, 0))),
    'o': (350, oval(350, 490)),
    'p': (350, path((0, -200), (0, 490)), oval(350, 490)),
    'q': (350, oval(350, 490), path((350, 490), (350, -200))),
    'r': (240, path((0, 0), (0, 490)), path((0, 310), (0, 490, 160, 490), (205, 490, 240, 470))),
    's': (310, path((300, 440), (245, 490, 155, 490), (0, 490, 0, 365),
                    (0, 280, 155, 245), (310, 210, 310, 120),
                    (310, 0, 155, 0), (60, 0, 0, 55))),
    't': (240, path((85, 650), (85, 120), (85, 0, 185, 0), (240, 0)), path((0, 470), (240, 470))),
    'u': (350, path((0, 490), (0, 170), (0, 0, 175, 0), (350, 0, 350, 180)),
               path((350, 490), (350, 0))),
    'v': (350, path((0, 490), (175, 0), (350, 490))),
    'w': (540, path((0, 490), (115, 0), (270, 355), (425, 0), (540, 490))),
    'x': (340, path((0, 490), (340, 0)), path((0, 0), (340, 490))),
    'y': (350, path((0, 490), (175, 0)), path((350, 490), (145, -90), (100, -220, 0, -195))),
    'z': (330, path((0, 490), (330, 490), (0, 0), (330, 0))),
    '0': (360, oval(360), path((70, 140), (290, 560))),
    '1': (360, path((40, 550), (180, 700), (180, 0)), path((25, 0), (335, 0))),
    '2': (360, path((0, 560), (0, 700, 175, 700), (360, 700, 360, 535),
                    (360, 440, 225, 320), (0, 0), (360, 0))),
    '3': (360, path((0, 630), (80, 700, 175, 700), (350, 700, 350, 530),
                    (350, 350, 160, 350), (360, 350, 360, 175),
                    (360, 0, 175, 0), (75, 0, 0, 70))),
    '4': (360, path((280, 0), (280, 700), (0, 230), (360, 230))),
    '5': (360, path((350, 700), (30, 700), (15, 370), (90, 405, 165, 405),
                    (360, 405, 360, 200), (360, 0, 175, 0), (70, 0, 0, 70))),
    '6': (360, path((325, 650), (270, 700, 190, 700), (0, 700, 0, 310), (0, 0, 180, 0),
                    (360, 0, 360, 205), (360, 410, 180, 410), (0, 410, 0, 215))),
    '7': (360, path((0, 700), (360, 700), (80, 0))),
    '8': (360, oval(320, 330, 370), oval(360, 370)),
    '9': (360, path((35, 50), (90, 0, 170, 0), (360, 0, 360, 390), (360, 700, 180, 700),
                    (0, 700, 0, 495), (0, 290, 180, 290), (360, 290, 360, 485))),
    ' ': (190,),
    '.': (0, path((0, 0), (0, 5))),
    ',': (75, path((75, 30), (0, -120))),
    ':': (0, path((0, 80), (0, 85)), path((0, 420), (0, 425))),
    ';': (75, path((75, 80), (0, -70)), path((75, 420), (75, 425))),
    '!': (0, path((0, 700), (0, 200)), path((0, 0), (0, 5))),
    "'": (60, path((60, 700), (0, 550))),
    '-': (250, path((0, 280), (250, 280))),
    '/': (300, path((0, -40), (300, 740))),
    '(': (160, path((160, 740), (0, 570, 0, 350), (0, 130, 160, -40))),
    ')': (160, path((0, 740), (160, 570, 160, 350), (160, 130, 0, -40))),
}
for accented, base, accent in (('è', 'e', path((105, 725), (235, 615))),
                               ('ō', 'o', path((60, 650), (290, 650))),
                               ('ū', 'u', path((60, 650), (290, 650)))):
    GLYPHS[accented] = (*GLYPHS[base], accent)
CHARACTERS = ''.join(sorted(GLYPHS))


def _arc(pen, center, radius, start, sweep):
    """Quadratic approximation to a round cap, in at most 45 degree pieces."""
    steps = max(1, round(abs(sweep)/(pi/4)))
    for i in range(steps):
        a, b = start+sweep*i/steps, start+sweep*(i+1)/steps
        middle, reach = (a+b)/2, radius/cos((b-a)/2)
        pen.qCurveTo((center[0]+reach*cos(middle), center[1]+reach*sin(middle)),
                     (center[0]+radius*cos(b), center[1]+radius*sin(b)))


def _stroke(pen, points, radius):
    """Expand each line/curve into a clockwise capsule using nonzero winding.

    Segment contours overlap at joins, as allowed by TrueType. Each curved
    side is fitted with four quadratics through offset endpoints/midpoints.
    Round caps cover the joins without an external geometry dependency.
    """
    start = points[0]
    for segment in points[1:]:
        end = segment[-2:]
        control = segment[:2] if len(segment) == 4 else None

        def offset(t, side):
            if control is None:
                x, y = (start[i]+t*(end[i]-start[i]) for i in (0, 1))
                dx, dy = end[0]-start[0], end[1]-start[1]
            else:
                x, y = ((1-t)**2*start[i]+2*t*(1-t)*control[i]+t*t*end[i] for i in (0, 1))
                dx, dy = (2*((1-t)*(control[i]-start[i])+t*(end[i]-control[i])) for i in (0, 1))
            length = hypot(dx, dy)
            return x-side*radius*dy/length, y+side*radius*dx/length

        def side(sign, reverse=False):
            count = 4 if control else 1
            for i in range(count):
                a, b = i/count, (i+1)/count
                if reverse:
                    a, b = 1-a, 1-b
                p, q = offset(a, sign), offset(b, sign)
                if control:
                    m = offset((a+b)/2, sign)
                    pen.qCurveTo((2*m[0]-(p[0]+q[0])/2, 2*m[1]-(p[1]+q[1])/2), q)
                else:
                    pen.lineTo(q)

        pen.moveTo(offset(0, 1))
        side(1)
        normal = offset(1, 1)
        _arc(pen, end, radius, atan2(normal[1]-end[1], normal[0]-end[0]), -pi)
        side(-1, reverse=True)
        normal = offset(0, -1)
        _arc(pen, start, radius, atan2(normal[1]-start[1], normal[0]-start[0]), -pi)
        pen.closePath()
        start = end


@cache
def stroke_face(weight='bold'):
    """Return cap height and (recording, advance, bounds) by character."""
    if weight not in WEIGHTS:
        raise ValueError('Unknown text weight: '+weight)
    radius = WEIGHTS[weight]/2
    vertical_scale = (CAP_HEIGHT-2*radius)/CAP_HEIGHT
    result = {}
    for char, (width, *strokes) in GLYPHS.items():
        pen = RecordingPen()
        for stroke in strokes:
            points = []
            for segment in stroke:
                points.append(tuple(value+70 if i % 2 == 0 else radius+value*vertical_scale
                                    for i, value in enumerate(segment)))
            _stroke(pen, points, radius)
        bounds = BoundsPen(None)
        pen.replay(bounds)
        result[char] = pen.value, width+140, bounds.bounds
    return CAP_HEIGHT, result


@cache
def face(weight='bold'):
    """Load our bundled, merged outlines; consumers only need FontTools."""
    if weight not in WEIGHTS:
        raise ValueError('Unknown text weight: '+weight)
    result = {}
    with TTFont(FONT_DIR/f'GameSans-{weight.title()}.ttf') as font:
        glyphs = font.getGlyphSet()
        for code, name in font.getBestCmap().items():
            pen = DecomposingRecordingPen(glyphs)
            glyphs[name].draw(pen)
            bounds = BoundsPen(None)
            pen.replay(bounds)
            result[chr(code)] = pen.value, font['hmtx'][name][0], bounds.bounds
        return font['OS/2'].sCapHeight, result


def build_font(output, weight='regular'):
    """Build a reusable standalone TTF from exactly the same original outlines."""
    from fontTools.ttLib.removeOverlaps import removeOverlaps
    _, alphabet = stroke_face(weight)
    order = ['.notdef']+[f'uni{ord(c):04X}' for c in CHARACTERS]
    glyphs, metrics = {'.notdef': TTGlyphPen(None).glyph()}, {'.notdef': (500, 0)}
    for char, name in zip(CHARACTERS, order[1:]):
        pen = TTGlyphPen(None)
        recording, advance, bounds = alphabet[char]
        replayRecording(recording, pen)
        glyph = pen.glyph()
        if glyph.numberOfContours:
            # Signal intentional overlapping stroke contours to rasterizers.
            glyph.flags[0] |= 0x40
        glyphs[name], metrics[name] = glyph, (advance, round(bounds[0]) if bounds else 0)
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder(order)
    builder.setupCharacterMap({ord(c): n for c, n in zip(CHARACTERS, order[1:])})
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics(metrics)
    builder.setupHorizontalHeader(ascent=900, descent=-250)
    style = weight.title()
    psname = FAMILY.replace(' ', '')+'-'+style
    builder.setupNameTable(dict(familyName=FAMILY, styleName=style, fullName=FAMILY+' '+style,
        psName=psname, uniqueFontIdentifier=psname+'-1.0', version='Version 1.0',
        copyright=COPYRIGHT, description=DESCRIPTION,
        licenseDescription='Licensed under the Apache License, Version 2.0',
        licenseInfoURL='https://www.apache.org/licenses/LICENSE-2.0'))
    builder.setupOS2(sTypoAscender=900, sTypoDescender=-250, usWinAscent=900, usWinDescent=250,
                     sCapHeight=CAP_HEIGHT, sxHeight=round(WEIGHTS[weight]/2+490*(700-WEIGHTS[weight])/700),
                     usWeightClass=700 if weight == 'bold' else 400,
                     fsType=0, fsSelection=0x20 if weight == 'bold' else 0x40)
    builder.setupPost()
    builder.setupHead(macStyle=1 if weight == 'bold' else 0, created=3875644800, modified=3875644800)
    builder.setupMaxp()
    # Merge stroke joins once in the base, keeping every game font compact and
    # giving rasterizers simple contours without intentional overlaps.
    removeOverlaps(builder.font)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    builder.font.save(output)
    builder.font.close()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=FONT_DIR)
    args = parser.parse_args()
    for weight in WEIGHTS:
        output = args.output_dir/f'GameSans-{weight.title()}.ttf'
        build_font(output, weight)
        print(f'Saved {output}: {len(CHARACTERS)} characters, {output.stat().st_size:,} bytes')
