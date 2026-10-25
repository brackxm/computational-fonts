# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Build standard Dodgem with an exact opponent on either side."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'shared'))
from exactgame import build_game
from fontgame import rect, circle
from game_text import centered_lettering
import model

CELL, LEFT, BOTTOM = 220, 570, 350


def frame(p, s):
    centered_lettering(p, 'Dodgem', s+900, 1140, 20)
    centered_lettering(p, 'Red exits north', s+900, 1060, 9, weight='regular')
    for i in range(4):
        rect(p, s+LEFT+i*CELL, BOTTOM, 3, 3*CELL)
        rect(p, s+LEFT, BOTTOM+i*CELL, 3*CELL, 3)
    for i in range(3):
        centered_lettering(p, chr(65+i), s+LEFT+i*CELL+110, BOTTOM-60, 10)
        centered_lettering(p, str(i+1), s+LEFT-45, BOTTOM+i*CELL+95, 10)
    centered_lettering(p, 'Blue exits east', s+900, 230, 9, weight='regular')


def paint(f, board):
    parts = []
    for i, piece in enumerate(board):
        if piece == '.':
            continue
        name = f'car_{piece}_{i}'
        if name not in f.glyphs:
            def car(p, s, i=i, piece=piece):
                x, y = s+LEFT+i%3*CELL+110, BOTTOM+i//3*CELL+110
                if piece == '0':
                    rect(p, x-65, y-35, 120, 70)
                    for dy in (-42, 42):
                        circle(p, x-35, y+dy, 13)
                        circle(p, x+30, y+dy, 13)
                    rect(p, x+50, y-12, 25, 24)
                else:
                    rect(p, x-35, y-65, 70, 120)
                    for dx in (-42, 42):
                        circle(p, x+dx, y-35, 13)
                        circle(p, x+dx, y+30, 13)
                    rect(p, x-12, y+50, 24, 25)
            f.add(name, car)
        parts.append((name, 1 if piece == '0' else 2))
    return parts


def highlight(f, token):
    square = token[:2] if token[2] == 'X' else token[2:4]
    x, y = ord(square[0])-65, int(square[1])-1
    def draw(p, s):
        a, b = s+LEFT+x*CELL+5, BOTTOM+y*CELL+5
        for dx, dy, w, h in ((0, 0, CELL-10, 5), (0, CELL-15, CELL-10, 5), (0, 0, 5, CELL-10), (CELL-15, 0, 5, CELL-10)):
            rect(p, a+dx, b+dy, w, h)
        centered_lettering(p, 'Font: '+token[:-1], s+900, 100, 10)
    return f.add('r_last_'+token[:-1], draw, color=3)


def build_font(output):
    return build_game(model, 'Dodgem', output, frame, paint, highlight, share_contours=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path(__file__).with_name('dodgem-font.ttf'))
    build_font(parser.parse_args().output)
