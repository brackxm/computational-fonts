# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Render the bundled original base fonts for visual review. Requires Pillow."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def render(output=HERE/'specimen.png'):
    image = Image.new('RGB', (1450, 1190), '#faf8f1')
    draw = ImageDraw.Draw(image)

    def text(value, x, y, size, weight='Regular', color='#243f43'):
        font = ImageFont.truetype(str(HERE/f'GameSans-{weight}.ttf'), size)
        draw.text((x, y), value, font=font, fill=color)

    text('Game Sans', 45, 22, 65, 'Bold')
    text('Original lettering for computational games / 76 characters', 48, 105, 27)
    samples = (
        ('ABCDEFGHIJKLMNOPQRSTUVWXYZ', 41),
        ('abcdefghijklmnopqrstuvwxyz', 41),
        ('0123456789   0O 1Il   è ō ū', 41),
        ("! ' ( ) , - . / : ;", 37),
        ('Mū tōrere   Misère Nim   Hexapawn', 41),
        ('Your turn    Font wins    Invalid move', 35),
        ('First 2    Second 2    Font: A1 to B2', 35),
        ('Rain taps the glass roof. A south gate needs power and a crystal.', 27),
        ('Inventory: key, lamp / Power: on', 27),
    )
    for weight, top in (('Regular', 168), ('Bold', 666)):
        draw.line((48, top, 1402, top), fill='#c8d2cd', width=1)
        text(weight+' / '+('400' if weight == 'Regular' else '700'), 48, top+12, 23,
             weight, '#207d79')
        y = top+55
        for value, size in samples:
            text(value, 48, y, size, weight)
            y += 49
    image.save(output)
    print(output)


def render_comparison(output=HERE/'comparison.png'):
    """Compare the two bundled families at the game helper's equal cap height.

    Draw one character at a time with nominal advances, matching game_text.py
    and the previous Roboto helper: neither applies kerning or text ligatures.
    """
    roboto = ROOT/'decoders/shared/fonts/roboto-2'
    image = Image.new('RGB', (1740, 1530), '#faf8f1')
    draw = ImageDraw.Draw(image)
    ink, muted, rule = '#243f43', '#55706d', '#d7dfd9'
    ui = lambda size: ImageFont.truetype(str(roboto/'Roboto-Regular.ttf'), size)
    draw.text((55, 36), 'The same game labels, side by side', font=ui(43), fill=ink)
    draw.text((57, 100), 'Matched capital height, baseline and weight. Original spacing; no kerning.',
              font=ui(24), fill=muted)
    columns = (('Game Sans', HERE, 'GameSans', 58), ('Roboto 2', roboto, 'Roboto', 922))
    for family, _, _, x in columns:
        draw.text((x, 164), family, font=ui(36), fill=ink)
    draw.line((865, 160, 865, 1445), fill=rule, width=2)
    samples = (
        ('Hexapawn', 38),
        ('Mū tōrere', 38),
        ('Misère Nim', 38),
        ("Wythoff's Nim", 34),
        ('Your turn    Font wins', 29),
        ('Invalid move    Check your input', 26),
        ('First 2    Second 2', 29),
        ('Font: A1 to B2', 29),
        ('Rain taps the glass roof.', 25),
    )
    for weight, top in (('Regular', 235), ('Bold', 842)):
        draw.line((58, top-10, 1682, top-10), fill=rule, width=2)
        for family, directory, prefix, x in columns:
            draw.text((x, top+4), weight+' / '+('400' if weight == 'Regular' else '700'),
                      font=ui(23), fill='#207d79')
            baseline = top+99
            for label, cap_height in samples:
                path = directory/f'{prefix}-{weight}.ttf'
                with TTFont(path) as face:
                    size = round(cap_height*face['head'].unitsPerEm/face['OS/2'].sCapHeight)
                font = ImageFont.truetype(str(path), size)
                cursor = x
                for char in label:
                    draw.text((cursor, baseline), char, font=font, fill=ink, anchor='ls')
                    cursor += font.getlength(char)
                if cursor > x+755:
                    raise ValueError(f'Comparison label overflows {family}: {label}')
                baseline += 56
    draw.text((58, 1472), 'Game Sans: original outlines by Michael Brackx. Roboto: Copyright 2015 Google Inc. Both Apache 2.0.',
              font=ui(21), fill=muted)
    image.save(output)
    print(output)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compare', action='store_true', help='Compare Game Sans with bundled Roboto 2')
    args = parser.parse_args()
    render_comparison() if args.compare else render()
