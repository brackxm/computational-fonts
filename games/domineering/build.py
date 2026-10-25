# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Build perfect 4x4 Domineering for either side."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'shared'))
from exactgame import build_game
from fontgame import rect
from game_text import centered_lettering
import model

CELL, LEFT, BOTTOM = 170, 560, 330


def frame(p, s):
    centered_lettering(p, 'Domineering', s+900, 1140, 20)
    centered_lettering(p, 'First: vertical    Second: horizontal', s+900, 1070, 9, weight='regular')
    for i in range(5):
        rect(p, s+LEFT+i*CELL, BOTTOM, 3, 4*CELL)
        rect(p, s+LEFT, BOTTOM+i*CELL, 4*CELL, 3)
    for i in range(4):
        centered_lettering(p, chr(65+i), s+LEFT+i*CELL+85, BOTTOM-60, 10)
        centered_lettering(p, str(i+1), s+LEFT-45, BOTTOM+i*CELL+65, 10)


def paint(f, board):
    parts = []
    for side, occupied in enumerate(board):
        delta = 4 if side == 0 else 1
        while occupied:
            i = (occupied & -occupied).bit_length()-1
            occupied ^= (1 << i) | (1 << (i+delta))
            name = f'domino_{side}_{i}'
            if name not in f.glyphs:
                def draw(p, s, i=i, side=side):
                    x, y = s+LEFT+i%4*CELL+8, BOTTOM+i//4*CELL+8
                    rect(p, x, y, CELL*(2 if side else 1)-16, CELL*(1 if side else 2)-16)
                f.add(name, draw)
            parts.append((name, 1 if side == 0 else 2))
    return parts


def highlight(f, token):
    x, y = ord(token[0])-65, int(token[1])-1
    w, h = (CELL, 2*CELL) if token[2] == 'V' else (2*CELL, CELL)
    def draw(p, s):
        a, b = s+LEFT+x*CELL+4, BOTTOM+y*CELL+4
        for dx, dy, width, height in ((0, 0, w-8, 5), (0, h-13, w-8, 5), (0, 0, 5, h-8), (w-13, 0, 5, h-8)):
            rect(p, a+dx, b+dy, width, height)
        centered_lettering(p, 'Font: '+token[:-1], s+900, 100, 10)
    return f.add('r_last_'+token[:-1], draw, color=3)


def build_font(output):
    return build_game(model, 'Domineering', output, frame, paint, highlight, share_contours=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path(__file__).with_name('domineering-font.ttf'))
    build_font(parser.parse_args().output)
