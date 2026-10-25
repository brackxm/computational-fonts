# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Build perfect 2x2-box Dots and Boxes with scoring and bonus turns."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'shared'))
from exactgame import build_game
from fontgame import rect, circle
from game_text import centered_lettering
import model

GAP, LEFT, BOTTOM = 260, 640, 410


def frame(p, s):
    centered_lettering(p, 'Dots and Boxes', s+900, 1140, 20)
    centered_lettering(p, 'Complete a box and play again', s+900, 1070, 9, weight='regular')
    for y in range(3):
        for x in range(3):
            circle(p, s+LEFT+x*GAP, BOTTOM+y*GAP, 12)
    for i in range(3):
        centered_lettering(p, chr(65+i), s+LEFT+i*GAP, BOTTOM-65, 10)
        centered_lettering(p, str(i+1), s+LEFT-65, BOTTOM+i*GAP-15, 10)


def segment(p, s, token, thickness=8):
    x, y = s+LEFT+(ord(token[0])-65)*GAP, BOTTOM+(int(token[1])-1)*GAP
    if token[2] == 'H':
        rect(p, x, y-thickness//2, GAP, thickness)
    else:
        rect(p, x-thickness//2, y, thickness, GAP)


def paint(f, board):
    edges, owners = board
    parts = []
    for token, index in model.EDGES.items():
        if not edges & (1 << index):
            continue
        name = 'edge_'+str(index)
        if name not in f.glyphs:
            f.add(name, lambda p, s, token=token: segment(p, s, token))
        parts.append((name, 0))
    for i, owner in enumerate(owners):
        if owner == -1:
            continue
        name = f'box_{owner}_{i}'
        if name not in f.glyphs:
            def draw(p, s, i=i, owner=owner):
                x, y = s+LEFT+(i%2+.5)*GAP, BOTTOM+(i//2+.5)*GAP
                circle(p, x, y, 60)
                if owner == 1:
                    circle(p, x, y, 42, True)
            f.add(name, draw)
        parts.append((name, 1 if owner == 0 else 2))
    a, b = model.scores(board)
    score = f'score_{a}_{b}'
    if score not in f.glyphs:
        f.add(score, lambda p, s, a=a, b=b: centered_lettering(p, f'First {a}    Second {b}', s+900, 260, 9))
    parts.append((score, 0))
    return parts


def highlight(f, token):
    def draw(p, s):
        segment(p, s, token, 15)
        centered_lettering(p, 'Font: '+token[:-1], s+900, 100, 10)
    return f.add('r_last_'+token[:-1], draw, color=3)


def build_font(output):
    return build_game(model, 'Dots and Boxes', output, frame, paint, highlight, share_contours=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path(__file__).with_name('dots-and-boxes-font.ttf'))
    build_font(parser.parse_args().output)
