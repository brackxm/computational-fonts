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
import build
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'shared'))
from native_font import NativeFont,transport

FONT=Path(__file__).resolve().with_name('tic-tac-toe-font.ttf')
BOARDS=build.positions();IDS={board:i for i,board in enumerate(BOARDS)}
WIN_MASKS=(7,56,448,73,146,292,273,84)


def masks(board):return tuple(sum(1<<i for i,c in enumerate(board) if c==side) for side in 'xo')


def reference_winner(x,o):
    for side,bits in (('x',x),('o',o)):
        if any(bits&line==line for line in WIN_MASKS):return side
    return '=' if x|o==511 else None


def reference_moves(x,o,side):
    if reference_winner(x,o) is not None:return {}
    return {str(i+1):(x|1<<i,o) if side=='x' else (x,o|1<<i) for i in range(9) if not (x|o)>>i&1}


@lru_cache(None)
def reference(x,o,side):
    end=reference_winner(x,o)
    if end is not None:return (0 if end=='=' else 1 if end==side else -1),0
    other='o' if side=='x' else 'x'
    options=[(-v,d+1) for xx,oo in reference_moves(x,o,side).values() for v,d in [reference(xx,oo,other)]]
    best=max(v for v,d in options);distances=[d for v,d in options if v==best]
    return best,min(distances) if best==1 else max(distances)


class TicTacToeTests(unittest.TestCase):
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

    def test_independent_complete_solution(self):
        pending=[(0,0,'x')];seen=set(pending)
        while pending:
            x,o,side=pending.pop();other='o' if side=='x' else 'x'
            for xx,oo in reference_moves(x,o,side).values():
                node=xx,oo,other
                if node not in seen:seen.add(node);pending.append(node)
        self.assertEqual(len(seen),5478)
        self.assertEqual(seen,{(*masks(board),side) for board,side in model.graph()})
        self.assertEqual(model.solve(model.INITIAL,'x'),(0,9))
        for board,side in model.graph():
            x,o=masks(board)
            self.assertEqual(model.winner(board),reference_winner(x,o))
            self.assertEqual(model.solve(board,side),reference(x,o,side))
            self.assertEqual({key:masks(child) for key,child in model.moves(board,side).items()},reference_moves(x,o,side))
            if model.winner(board) is not None:
                self.assertIsNone(model.choose(board,side));continue
            key=model.choose(board,side);value,distance=model.solve(board,side)
            self.assertEqual(model.solve(model.moves(board,side)[key],model.opponent(side)),(-value,distance-1))
        # Policy compression must retain every possible human response.
        policy=set(model.policy_graph());self.assertEqual(len(policy),121)
        self.assertIn((model.INITIAL,'x'),policy)
        self.assertIn((model.reply(model.INITIAL,'o')[0],'o'),policy)
        for board,human in policy:
            self.assertLessEqual(model.solve(board,human)[0],0)
            for child in model.moves(board,human).values():
                after,last,status=model.reply(child,human)
                if status=='ready':self.assertIn((after,human),policy)
                self.assertNotEqual(status,'human_won')

    def test_every_compiled_cursor_and_input(self):
        with TTFont(FONT) as font:
            codes={name:chr(0xf0000+i) for i,name in enumerate(font.getGlyphOrder())}
            table=CmapSubtable.newSubtable(12);table.platformID,table.platEncID,table.language=3,10,0
            table.cmap=dict(font.getBestCmap());table.cmap.update({ord(c):name for name,c in codes.items()})
            font['cmap'].tables.append(table)
            with tempfile.TemporaryDirectory() as temp:
                path=Path(temp)/'test.ttf';font.save(path);native=NativeFont(path)
                try:
                    def run(state,source,last='r_last_none'):
                        return self.decode(native.shape_text(codes['board']+codes[state]+codes[last]+transport(source)[1:]))
                    for board,human in model.policy_graph():
                        state=f'r_active_{human}_{IDS[board]}';options=model.moves(board,human)
                        for code in range(32,128):
                            key=chr(code)
                            expected=(board,None,'ready') if key==' ' else (
                                model.reply(options[key],human) if key in options else
                                (board,None,'invalid' if key in '123456789' else 'malformed'))
                            self.assertEqual(run(state,key),expected,(board,human,key))
                        latest=model.reply(options['1'],human)[1] if '1' in options else None
                        self.assertEqual(run(state,'1','r_last_9')[1],latest or '9')
                    for name in codes:
                        if name.startswith(('r_invalid_','r_malformed_','r_computer_won_','r_draw_')):
                            status=name[2:].rsplit('_',2)[0];board=BOARDS[int(name.rsplit('_',1)[1])]
                            self.assertEqual(run(name,'123456789bad🙂'*2),(board,None,status),name)
                finally:native.close()

    def test_every_human_history_both_sides(self):
        counts=[]
        for mode in 'hb':
            terminal=[];prefixes=[]
            def visit(source):
                prefixes.append(source);self.check_source(source)
                board,last,status=model.replay(source)
                if status!='ready':
                    terminal.append(status);self.check_source(source+'123🙂\ue000bad')
                    return
                for key in model.moves(board,'x' if mode=='h' else 'o'):visit(source+key)
            visit(mode);counts.append((len(prefixes),len(terminal)))
            self.assertEqual(set(terminal),{'draw','computer_won'})
        self.assertEqual(counts,[(850,521),(119,92)])
        self.assertEqual(self.shape('h12768')[2],'draw')
        self.assertEqual(self.shape('b1762')[2],'draw')

    def test_syntax_errors_and_terminal_freeze(self):
        for source in ('','h','b','H','bad','h0','h1','h11','h15','b5','h124','b12','h12768',
                       'h127681234bad🙂','h🙂','h\ue000','h\0','h\x7f','h:','h９','h\u202e1',
                       ' h 1\n2\t7\r6 8 ', 'b 1 7 6 2 ignored🙂'):
            self.check_source(source)

    def test_font_protocol_and_metadata(self):
        args=['hb-shape',str(FONT),'--text='+model.START+'h12768'+model.END,'--output-format=json']
        shaped=json.loads(subprocess.check_output(args,text=True));self.assertEqual(sum(g['ax'] for g in shaped),1807)
        shaped=json.loads(subprocess.check_output(args+['--features=-liga'],text=True))
        self.assertFalse(any(g['g'].startswith('status_') for g in shaped))
        with TTFont(FONT) as font:
            self.assertEqual(font['head'].unitsPerEm,1000);self.assertEqual(font['OS/2'].fsType,0)
            self.assertEqual(len(font['CPAL'].palettes[0]),4)


if __name__=='__main__':unittest.main()
