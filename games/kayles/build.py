# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Build perfect twelve-pin Kayles, with either player moving first."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'shared'))
from exactgame import build_game
from fontgame import rect, circle
from game_text import centered_lettering
import model

GAP, LEFT = 120, 240


def frame(p, s):
    centered_lettering(p, 'Kayles', s+900, 1130, 20)
    centered_lettering(p, 'One pin or two original neighbors', s+900, 1030, 9, weight='regular')
    for i in range(model.PINS):
        centered_lettering(p, f'{i+1:02}', s+LEFT+i*GAP, 370, 10)
        rect(p, s+LEFT+i*GAP-16, 450, 32, 4)


def paint(f, mask):
    parts = []
    for i in range(model.PINS):
        if not mask & (1 << i):
            continue
        name = f'pin_{i}'
        if name not in f.glyphs:
            def pin(p, s, i=i):
                x = s+LEFT+i*GAP
                circle(p, x, 800, 30)
                rect(p, x-16, 710, 32, 75)
                circle(p, x, 625, 42)
                rect(p, x-42, 500, 84, 125)
            f.add(name, pin)
        parts.append((name, 1))
    return parts


def highlight(f, token):
    i = int(token[:2])-1
    count = 1 if token[2] == 'S' else 2
    def draw(p, s):
        x, w = s+LEFT+i*GAP-50, GAP*(count-1)+100
        for dx, dy, width, height in ((0, 0, w, 5), (0, 365, w, 5), (0, 0, 5, 370), (w-5, 0, 5, 370)):
            rect(p, x+dx, 480+dy, width, height)
        centered_lettering(p, 'Font: '+token[:-1], s+900, 100, 10)
    return f.add('r_last_'+token[:-1], draw, color=3)


def build_font(output):
    return build_game(model, 'Kayles', output, frame, paint, highlight, share_contours=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path(__file__).with_name('kayles-font.ttf'))
    build_font(parser.parse_args().output)
