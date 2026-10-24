# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Test helpers for the frozen font. No move generation beyond Python rule checks."""
import json
from pathlib import Path
import re
import struct
import sys

import uharfbuzz as hb

HERE = Path(__file__).resolve().parent
from build import glyph_order
sys.path.insert(0, str(HERE.parent))
import model


def encode(source, nonce=0):
    chars = [ord(c) if ' ' <= c <= '~' else 32 if c in '\t\r\n' else 127 for c in source]
    return '\ue000' + ''.join(chr(0xe100 + c) for c in chars) + '\ue120' * (256 * (len(source) + 1) + nonce) + '\ue001'


def decode(names):
    cells, statuses, last = {}, [], []
    for name in names:
        match = re.fullmatch(r'r_cell_(\d+)_(empty|[KQRBNPkqrbnp])', name)
        if match:
            index = int(match[1])
            assert index not in cells
            cells[index] = '.' if match[2] == 'empty' else match[2]
        if name.startswith('status_'):
            statuses.append(int(name[7:]))
        if name.startswith('r_last_'):
            last.append(name[7:])
    assert len(cells) == 25 and len(statuses) == len(last) == 1 and len(names) == 28
    return ''.join(cells[i] for i in range(25)), None if last[0] == 'none' else last[0], statuses[0]


class Font:
    def __init__(self, path):
        self.order = glyph_order(json.loads((HERE / 'manifest.json').read_text()))
        self.font = hb.Font(hb.Face(Path(path).read_bytes()))

    def shape(self, source, nonce=0):
        buffer = hb.Buffer()
        buffer.add_str(encode(source, nonce))
        buffer.direction, buffer.script = 'ltr', 'Latn'
        hb.shape(self.font, buffer, {'liga': True})
        return decode([self.order[g.codepoint] for g in buffer.glyph_infos])


def move_text(code):
    return model.square(code // 125) + model.square(code // 5 % 25) + ('', 'q', 'r', 'b', 'n')[code % 5]


def mirror(board):
    return ''.join(board[row:row+5][::-1] for row in range(0, 25, 5))


class Policy:
    """Read the supplied acyclic binary policy; never search or improve moves."""
    def __init__(self, tree):
        self.data = Path(tree).read_bytes()
        header = struct.unpack_from('<20I', self.data)
        assert header[0] == 0x47524232 and header[6] == 2
        self.root, self.widths = header[4], header[7:20]
        self.labels = struct.unpack_from('<' + str(header[3]) + 'I', self.data, 80)
        self.offset = 80 + 4 * len(self.labels)

    def query(self, board):
        flip = 25 - board.count('.') <= 5 and (board.index('K') % 5 > 2 or board.index('K') % 5 == 2 and board.index('k') % 5 > 2)
        canonical = mirror(board) if flip else board
        values = []
        for kind, width in zip('.PNBRQKpnbrqk'[1:], self.widths[1:]):
            positions = [i for i, piece in enumerate(canonical) if piece == kind]
            assert len(positions) <= width
            values.extend(positions + [25] * (width - len(positions)))
        xy = [45 if value == 25 else value % 5 | (value // 5 << 3) for value in values]
        node = self.root
        while node >= 0:
            feature, left, right = struct.unpack_from('<3i', self.data, self.offset + 12 * node)
            node = right if xy[feature // 6] >> (feature % 6) & 1 else left
            assert node != -(2**31), 'Missing frozen policy edge'
        bound, code = divmod(self.labels[-1-node], 3125)
        if flip and bound != 250:
            def square(s):
                return s // 5 * 5 + 4 - s % 5
            code = (square(code // 125) * 25 + square(code // 5 % 25)) * 5 + code % 5
        return bound, code
