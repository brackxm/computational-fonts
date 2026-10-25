# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Build exact three-counter Achi, including drawing cycles and draw offers."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'shared'))
from exactgame import build_game
from fontgame import rect, circle
from game_text import centered_lettering
import model

GAP, LEFT, BOTTOM = 270, 630, 410


def frame(p, s):
    centered_lettering(p, 'Achi', s+900, 1140, 20)
    centered_lettering(p, 'Three counters each', s+900, 1080, 9, weight='regular')
    for i in range(3):
        rect(p, s+LEFT+i*GAP-2, BOTTOM, 4, 2*GAP)
        rect(p, s+LEFT, BOTTOM+i*GAP-2, 2*GAP, 4)
        centered_lettering(p, chr(65+i), s+LEFT+i*GAP, BOTTOM-125, 9)
        centered_lettering(p, str(i+1), s+LEFT-100, BOTTOM+i*GAP-15, 10)
    for points in (((LEFT, BOTTOM-3), (LEFT+2*GAP, BOTTOM+2*GAP-3), (LEFT+2*GAP, BOTTOM+2*GAP+3), (LEFT, BOTTOM+3)),
                   ((LEFT, BOTTOM+2*GAP-3), (LEFT+2*GAP, BOTTOM-3), (LEFT+2*GAP, BOTTOM+3), (LEFT, BOTTOM+2*GAP+3))):
        p.moveTo((s+points[0][0], points[0][1]))
        for x, y in points[1:]:
            p.lineTo((s+x, y))
        p.closePath()


def paint(f, board):
    parts = []
    for i, piece in enumerate(board):
        if piece == '.':
            continue
        name = f'counter_{piece}_{i}'
        if name not in f.glyphs:
            def draw(p, s, i=i, piece=piece):
                x, y = s+LEFT+i%3*GAP, BOTTOM+i//3*GAP
                circle(p, x, y, 64)
                if piece == '1':
                    circle(p, x, y, 43, True)
            f.add(name, draw)
        parts.append((name, 1 if piece == '0' else 2))
    phase = 'Place' if board.count('.') > 3 else 'Slide'
    if 'phase_'+phase not in f.glyphs:
        f.add('phase_'+phase, lambda p, s: centered_lettering(p, phase, s+900, 1025, 8))
    parts.append(('phase_'+phase, 0))
    return parts


def highlight(f, token):
    target = token[-3:-1]
    i = (int(target[1])-1)*3+ord(target[0])-65
    def draw(p, s):
        circle(p, s+LEFT+i%3*GAP, BOTTOM+i//3*GAP, 84)
        circle(p, s+LEFT+i%3*GAP, BOTTOM+i//3*GAP, 78, True)
        centered_lettering(p, 'Font: '+token[:-1], s+900, 100, 10)
    return f.add('r_last_'+token[:-1], draw, color=3)


def build_font(output):
    return build_game(model, 'Achi', output, frame, paint, highlight, share_contours=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path(__file__).with_name('achi-font.ttf'))
    build_font(parser.parse_args().output)
