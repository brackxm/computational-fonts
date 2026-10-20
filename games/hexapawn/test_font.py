# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
from functools import lru_cache
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable
import model
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'shared'))
from native_font import NativeFont,transport

FONT=Path(__file__).resolve().with_name('hexapawn-font.ttf')
BOARDS=tuple(sorted({board for board,side in model.graph()}))
IDS={board:i for i,board in enumerate(BOARDS)}


def masks(board):return tuple(sum(1<<i for i,c in enumerate(board) if c==side) for side in 'wb')


def reference_moves(white,black,side):
    own,enemy=(white,black) if side=='w' else (black,white)
    result={};direction=3 if side=='w' else -3
    for origin in range(9):
        if not own>>origin&1:continue
        target=origin+direction
        if 0<=target<9 and not (own|enemy)>>target&1:
            changed=own^(1<<origin)^(1<<target)
            result[origin,target]=(changed,enemy) if side=='w' else (enemy,changed)
        for delta in (-1,1):
            if not 0<=origin%3+delta<3:continue
            target=origin+direction+delta
            if 0<=target<9 and enemy>>target&1:
                changed=own^(1<<origin)^(1<<target);captured=enemy^(1<<target)
                result[origin,target]=(changed,captured) if side=='w' else (captured,changed)
    return result


def reference_winner(white,black,side):
    if white&448:return 'w'
    if black&7:return 'b'
    if not white:return 'b'
    if not black:return 'w'
    if not reference_moves(white,black,side):return 'b' if side=='w' else 'w'
    return None


@lru_cache(None)
def reference(white,black,side):
    end=reference_winner(white,black,side)
    if end:return (1 if end==side else -1),0
    other='b' if side=='w' else 'w'
    children=[reference(w,b,other) for w,b in reference_moves(white,black,side).values()]
    best=max(-v for v,d in children)
    distances=[d+1 for v,d in children if -v==best]
    return best,(min(distances) if best==1 else max(distances))


class HexapawnTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.native=NativeFont(FONT)
    @classmethod
    def tearDownClass(cls):cls.native.close()

    def decode(self,names):
        states=[n for n in names if n.startswith('r_') and not n.startswith('r_last_')]
        lasts=[n for n in names if n.startswith('r_last_')]
        statuses=[n[7:] for n in names if n.startswith('status_')]
        self.assertEqual((len(names),len(states),len(lasts),len(statuses)),(4,1,1,1),names)
        board=model.INITIAL if states[0]=='r_header' else BOARDS[int(states[0].rsplit('_',1)[1])]
        return board,None if lasts[0]=='r_last_none' else lasts[0].removeprefix('r_last_'),statuses[0]

    def shape(self,source):return self.decode(self.native.shape(source))
    def check_source(self,source):self.assertEqual(self.shape(source),model.replay(source),source)

    def test_independent_complete_graph(self):
        pending=[(7,448,'w')];seen=set(pending)
        while pending:
            white,black,side=pending.pop()
            if reference_winner(white,black,side):continue
            other='b' if side=='w' else 'w'
            for w,b in reference_moves(white,black,side).values():
                node=w,b,other
                if node not in seen:seen.add(node);pending.append(node)
        self.assertEqual(seen,{(*masks(board),side) for board,side in model.graph()})
        self.assertEqual(len(seen),135)
        self.assertEqual(sum(model.winner(b,s) is None for b,s in model.graph()),70)
        self.assertEqual(model.solve(model.INITIAL,'w'),(-1,6))
        for board,side in model.graph():
            w,b=masks(board)
            self.assertEqual(model.winner(board,side),reference_winner(w,b,side))
            self.assertEqual(model.solve(board,side),reference(w,b,side))
            if model.winner(board,side):continue
            actual={key:masks(child) for key,child in model.moves(board,side).items()}
            expected={model.square(origin)+model.square(target):child
                      for (origin,target),child in reference_moves(w,b,side).items()}
            self.assertEqual(actual,expected)
            for child in model.moves(board,side).values():
                self.assertLess(model.remaining_distance(child),model.remaining_distance(board))
            key=model.choose(board,side);value,distance=model.solve(board,side)
            self.assertEqual(model.solve(model.moves(board,side)[key],model.opponent(side)),(-value,distance-1))

    def test_every_compiled_action(self):
        with TTFont(FONT) as font:
            codes={name:chr(0xf0000+i) for i,name in enumerate(font.getGlyphOrder())}
            table=CmapSubtable.newSubtable(12);table.platformID,table.platEncID,table.language=3,10,0
            table.cmap=dict(font.getBestCmap());table.cmap.update({ord(c):name for name,c in codes.items()})
            font['cmap'].tables.append(table)
            with tempfile.TemporaryDirectory() as temp:
                path=Path(temp)/'test.ttf';font.save(path);native=NativeFont(path)
                try:
                    def run(state,source):
                        text=codes['board']+codes[state]+codes['r_last_none']+transport(source)[1:]
                        return self.decode(native.shape_text(text))
                    squares=[model.square(i) for i in range(9)]
                    for board,human in model.graph():
                        if model.winner(board,human):continue
                        state=f'r_active_{human}_{IDS[board]}';options=model.moves(board,human)
                        for origin in squares:
                            for target in squares:
                                key=origin+target
                                expected=model.reply(options[key],human) if key in options else (board,None,'invalid')
                                self.assertEqual(run(state,key),expected,(board,human,key))
                        self.assertEqual(run(state,'A1'),(board,None,'malformed'))
                    for name in codes:
                        if name.startswith(('r_invalid_','r_malformed_','r_computer_won_','r_human_won_')):
                            status=name[2:].rsplit('_',2)[0];board=BOARDS[int(name.rsplit('_',1)[1])]
                            self.assertEqual(run(name,'hA1A2bad'*3),(board,None,status),name)
                finally:native.close()

    def test_all_games_against_perfect_font(self):
        outcomes={}
        for mode in 'hb':
            terminal=[]
            def visit(source):
                self.check_source(source)
                board,last,status=model.replay(source)
                if status!='ready':
                    terminal.append(status);self.check_source(source+'A1A2🙂')
                    return
                for key in model.moves(board,'w' if mode=='h' else 'b'):visit(source+key)
            visit(mode);outcomes[mode]=set(terminal)
        self.assertEqual(outcomes['h'],{'computer_won'})
        self.assertIn('human_won',outcomes['b'])
        self.check_source('hB1B2C1B2A1A2')
        self.assertEqual(self.shape('bA3B2C3C2C2C1')[2],'human_won')

    def test_syntax_and_errors(self):
        for source in ('','h','b','hB1B2','hA1A3','hA1B2','hA1A1','hA3A2','hA1A2A1A2',
                       'hA1','hA1A','hA4A2','hD1A2','hA1a2','H','bad','h0','h🙂','h\ue000','h\0',
                       ' h B 1 B 2 \nC1\tB2\rA1 A2 ', 'bA3B2C3C2C2C1garbage🙂'):
            self.check_source(source)

    def test_metrics_palette_and_disabled_ligatures(self):
        args=['hb-shape',str(FONT),'--text='+model.START+'h'+model.END,'--output-format=json']
        output=json.loads(subprocess.check_output(args,text=True));self.assertEqual(sum(g['ax'] for g in output),1801)
        output=json.loads(subprocess.check_output(args+['--features=-liga'],text=True))
        self.assertFalse(any(g['g'].startswith('status_') for g in output))
        with TTFont(FONT) as font:
            self.assertEqual(font['head'].unitsPerEm,1000);self.assertEqual(font['OS/2'].fsType,0)
            self.assertEqual(len(font['CPAL'].palettes[0]),5)


if __name__=='__main__':unittest.main()
