# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Exhaustive strategy proof and native shaping checks (FontTools + HarfBuzz)."""
import ctypes
from functools import lru_cache
from io import BytesIO
from itertools import combinations_with_replacement
import json
from pathlib import Path
import random
import subprocess
import sys
import unittest

from fontTools.ttLib import TTFont
import model

HERE = Path(__file__).resolve().parent
FONT = HERE / 'notakto-font.ttf'
sys.path.insert(0, str(HERE.parents[1] / 'languages' / 'shared'))
from fontcircuit import harfbuzz as hb


class Shaper:
    def __init__(self, data=None):
        self.data = ctypes.create_string_buffer(data if data is not None else FONT.read_bytes())
        self.blob = hb.blob_create(self.data, len(self.data)-1, 2, None, None)
        self.face = hb.face_create(self.blob, 0)
        self.font = hb.font_create(self.face)
        with TTFont(FONT) as tt:
            self.order = tt.getGlyphOrder()

    def __call__(self, source):
        text = model.START + ''.join(chr(0xe100 + (ord(c) if ' ' <= c <= '~' else
                    32 if c in '\t\r\n' else 127)) for c in source) + model.END
        return self.run(text)

    def run(self, text):
        buffer = hb.buffer_create()
        try:
            hb.set_content(buffer, 1)
            for i, char in enumerate(text):
                hb.add(buffer, ord(char), i)
            hb.guess(buffer)
            hb.shape(self.font, buffer, None, 0)
            info = ctypes.cast(hb.getinfo(buffer, None), ctypes.POINTER(hb.GlyphInfo))
            names = [self.order[info[i].codepoint] for i in range(hb.length(buffer))]
            boards = [int(next(n for n in names if n.startswith(f'r_board{b}_')).rsplit('_',1)[1])
                      for b in range(3)]
            last = next(n for n in names if n.startswith('r_last_'))
            last = None if last == 'r_last_none' else tuple(map(int, last.split('_')[-2:]))
            statuses = [n[7:] for n in names if n.startswith('status_')]
            if len(statuses) != 1:
                raise AssertionError((source, names))
            return boards, last, statuses[0]
        finally:
            hb.buffer_destroy(buffer)

    def close(self):
        hb.font_destroy(self.font)
        hb.face_destroy(self.face)
        hb.blob_destroy(self.blob)


# A separate string-board solver checks the bitmask generator. Its rows,
# columns, diagonals, rotations, terminal rule, and successor construction are
# expressed independently, to avoid simply asserting the same implementation.
@lru_cache(None)
def normalize(board):
    if board == 'dead':
        return board
    lines = [board[i:i+3] for i in (0,3,6)] + [board[i::3] for i in range(3)]
    lines += [board[0]+board[4]+board[8], board[2]+board[4]+board[6]]
    if 'XXX' in lines:
        return 'dead'
    variants = []
    for _ in range(4):
        variants.extend((board, ''.join(board[r*3+c] for r in range(3) for c in (2,1,0))))
        board = ''.join(board[r*3+c] for c in range(3) for r in (2,1,0))
    return min(variants)


@lru_cache(None)
def reference(position):
    if all(b == 'dead' for b in position):
        return True
    for i, board in enumerate(position):
        if board == 'dead':
            continue
        for cell, mark in enumerate(board):
            if mark == '.':
                child = normalize(board[:cell]+'X'+board[cell+1:])
                if not reference(tuple(sorted(position[:i]+position[i+1:]+(child,)))):
                    return True
    return False


class NotaktoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shape = Shaper()

    @classmethod
    def tearDownClass(cls):
        cls.shape.close()

    def check_source(self, source):
        self.assertEqual(self.shape(source), model.replay(source), source)

    def test_independent_complete_strategy(self):
        boards = {mask: normalize(''.join('X' if mask >> i & 1 else '.' for i in range(9)))
                  for mask in model.BOARDS if mask != model.DEAD}
        boards[model.DEAD] = 'dead'
        for position in combinations_with_replacement(model.BOARDS, 3):
            self.assertEqual(model.winning(position), reference(tuple(sorted(boards[m] for m in position))), position)
        classes, representatives = model.strategy_classes()
        self.assertEqual(len(representatives), 8)
        self.assertTrue(model.winning((0,0,0)))
        for position in combinations_with_replacement(model.BOARDS, 3):
            reduced = tuple(sorted(representatives[classes[7 if m == model.DEAD else m]]
                                   for m in position))  # Mask 7 is a closed board.
            self.assertEqual(model.winning(position), model.winning(reduced))
            if model.winning(position) and any(m != model.DEAD for m in position):
                move = model.choose(position)
                self.assertIsNotNone(move)
                b,c = move
                self.assertFalse(model.dead(position[b]))
                self.assertFalse(position[b] >> c & 1)
                child = list(position)
                child[b] = model.CANONICAL[child[b] | 1 << c]
                self.assertFalse(model.winning(tuple(sorted(child))), position)

    def test_parser_and_legality(self):
        for source in ('', 'b', 'bad', 'bA1', 'bA2', 'bA', 'bA0', 'bD1', 'bB5',
                       'bA9C5', 'bA2B9', 'bA2A4', 'bA2A1', ' b\nA2\tB9 ',
                       'bb', 'B', 'b🙂', 'b\ue000', 'b\0', 'bA2!'):
            self.check_source(source)

    def test_all_human_continuations(self):
        terminals = 0
        @lru_cache(None)
        def visit(boards):
            nonlocal terminals
            for b,mask in enumerate(boards):
                if model.dead(mask):
                    continue
                for cell in range(9):
                    if mask >> cell & 1:
                        continue
                    child = list(boards); child[b] |= 1 << cell
                    if all(model.dead(m) for m in child):
                        terminals += 1
                        continue
                    move = model.choose(child)
                    self.assertIsNotNone(move)
                    child[move[0]] |= 1 << move[1]
                    self.assertFalse(all(model.dead(m) for m in child))
                    visit(tuple(child))
        visit((1,0,0))
        self.assertEqual(visit.cache_info().currsize, 400061)
        self.assertEqual(terminals, 921175)

    def test_every_compiled_decision_context(self):
        # Test-only cmap exposes internal registers; the shipped font does not.
        # Exercise each raw board mask against every pair of strategy classes,
        # in each board slot, including asymmetric positions and all D4 images.
        with TTFont(FONT) as font:
            codes = {name: chr(0xf0000+i) for i,name in enumerate(font.getGlyphOrder())}
            for table in font['cmap'].tables:
                if table.format == 12:
                    table.cmap.update({ord(code):name for name,code in codes.items()})
            # The production cmap needs only BMP. Add a format-12 test cmap.
            from fontTools.ttLib.tables._c_m_a_p import CmapSubtable
            table = CmapSubtable.newSubtable(12)
            table.platformID, table.platEncID, table.language = 3, 10, 0
            table.cmap = {ord(code):name for name,code in codes.items()}
            font['cmap'].tables.append(table)
            stream = BytesIO(); font.save(stream)
        shape = Shaper(stream.getvalue())
        try:
            _, representatives = model.strategy_classes()
            checked = set()
            for slot in range(3):
                for mask in range(512):
                    for left in representatives:
                        for right in representatives:
                            boards = [left,right]; boards.insert(slot,mask)
                            key = tuple(boards)
                            if key in checked or not model.winning(tuple(sorted(model.CANONICAL[m] for m in boards))):
                                continue
                            checked.add(key)
                            move = model.choose(boards)
                            if move is None:
                                continue
                            expected = list(boards); expected[move[0]] |= 1 << move[1]
                            names = ['board',*[f'r_board{b}_{m}' for b,m in enumerate(boards)],
                                     *[f'r_class{b}_0' for b in range(3)],'r_last_none','p_ai','end']
                            actual = shape.run(''.join(codes[name] for name in names))
                            self.assertEqual(actual,(expected,move,'ready'),boards)
        finally:
            shape.close()

    def test_complete_games_native_font(self):
        rng = random.Random(740)
        terminal = None
        for _ in range(300):
            source = 'b'
            while True:
                self.check_source(source)
                boards, _, status = model.replay(source)
                if status != 'ready':
                    self.assertEqual(status, 'computer_won')
                    terminal = source
                    break
                legal = [(b,c) for b,m in enumerate(boards) if not model.dead(m)
                         for c in range(9) if not m >> c & 1]
                b,c = rng.choice(legal)
                source += chr(65+b)+str(c+1)
        self.check_source(terminal+'A1garbage🙂')

    def test_ligatures_required_and_metrics(self):
        out = json.loads(subprocess.check_output(['hb-shape', str(FONT), '--text='+model.START+'b'+model.END,
                          '--features=-liga', '--output-format=json'], text=True))
        self.assertFalse(any(g['g'].startswith('status_') for g in out))
        out = json.loads(subprocess.check_output(['hb-shape', str(FONT), '--text='+model.START+'b'+model.END,
                          '--output-format=json'], text=True))
        self.assertEqual(sum(g['ax'] for g in out), 1801)
        with TTFont(FONT) as font:
            self.assertEqual(font['head'].unitsPerEm, 1000)
            self.assertIn('COLR', font)
            self.assertEqual(font['OS/2'].fsType, 0)


if __name__ == '__main__':
    unittest.main()
