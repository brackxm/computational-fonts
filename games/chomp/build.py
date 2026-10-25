# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Build a complete perfect Chomp opponent on a 6x5 chocolate bar."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'shared'))
from exactgame import build_game
from fontgame import rect
from game_text import centered_lettering
import model

CELL, LEFT, BOTTOM = 140, 480, 330


def frame(p, s):
    centered_lettering(p, 'Chomp', s+900, 1130, 20)
    for x in range(6):
        centered_lettering(p, chr(65+x), s+LEFT+x*CELL+CELL/2, BOTTOM-60, 10)
    for y in range(5):
        centered_lettering(p, str(y+1), s+LEFT-45, BOTTOM+y*CELL+50, 10)


def paint(f, rows):
    parts = []
    for y, length in enumerate(rows):
        for x in range(length):
            name = f'chocolate_{x}_{y}'
            if name not in f.glyphs:
                def draw(p, s, x=x, y=y):
                    a, b = s+LEFT+x*CELL+6, BOTTOM+y*CELL+6
                    rect(p, a, b, CELL-12, CELL-12)
                    if (x, y) == (0, 0):
                        # A cut-out X remains distinguishable in monochrome.
                        for i in range(5):
                            for j in {i, 4-i}:
                                rect(p, a+43+i*14, b+29+j*14, -14, 14)
                f.add(name, draw)
            parts.append((name, 2 if (x, y) == (0, 0) else 1))
    return parts


def highlight(f, token):
    x, y = ord(token[0])-65, int(token[1])-1
    def draw(p, s):
        a, b = s+LEFT+x*CELL, BOTTOM+y*CELL
        for dx, dy, w, h in ((0, 0, CELL, 5), (0, CELL-5, CELL, 5), (0, 0, 5, CELL), (CELL-5, 0, 5, CELL)):
            rect(p, a+dx, b+dy, w, h)
        centered_lettering(p, 'Font: '+token[:-1], s+900, 100, 10)
    return f.add('r_last_'+token[:-1], draw, color=3)


def build_font(output):
    return build_game(model, 'Chomp', output, frame, paint, highlight, share_contours=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path(__file__).with_name('chomp-font.ttf'))
    build_font(parser.parse_args().output)
