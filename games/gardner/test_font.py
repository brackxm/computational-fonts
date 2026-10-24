# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Compare real HarfBuzz execution with the separate Python rules model."""
from pathlib import Path
import random
import json
import subprocess
import re
import sys
import tempfile
import unittest

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable
import model
import protocol
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'shared'))
from native_font import NativeFont

FONT=Path(__file__).with_name('gardner-font.ttf')
STATUS={'ready':1,'font_win':2,'human_win':3,'invalid':4,'malformed':5,'draw':7}


def decode(names):
    cells={}
    for name in names:
        match=re.fullmatch(r'r_cell_(\d+)_(empty|[KQRBNPkqrbnp])',name)
        if match:
            i=int(match[1])
            if i in cells:raise AssertionError(('Duplicate display cell',i,names))
            cells[i]='.' if match[2]=='empty' else match[2]
    status=[int(n.removeprefix('status_')) for n in names if n.startswith('status_')]
    last=[n.removeprefix('r_last_') for n in names if n.startswith('r_last_')]
    if len(cells)!=25 or len(status)!=1 or len(last)!=1 or len(names)!=28:
        raise AssertionError(('Unfinished font execution',names))
    return ''.join(cells[i] for i in range(25)),None if last[0]=='none' else last[0],status[0]


class GardnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.book=model.load_book();cls.native=NativeFont(FONT)
        cls.temp=tempfile.TemporaryDirectory()
        # Test-only aliases permit arbitrary legal positions without making
        # extra entry points part of the public font protocol.
        with TTFont(FONT) as font:
            cls.codes={name:chr(0xf0000+i) for i,name in enumerate(font.getGlyphOrder())}
            cmap=CmapSubtable.newSubtable(12);cmap.platformID,cmap.platEncID,cmap.language=3,10,0
            cmap.cmap=dict(font.getBestCmap());cmap.cmap.update({ord(c):n for n,c in cls.codes.items()})
            font['cmap'].tables.append(cmap)
            path=Path(cls.temp.name)/'aliased.ttf';font.save(path)
        cls.injected=NativeFont(path)

    @classmethod
    def tearDownClass(cls):
        cls.native.close();cls.injected.close();cls.temp.cleanup()

    def expected(self,source):
        board,move,status,count=model.replay(source,self.book)
        return board,None if move is None else move[2:4],STATUS[status]

    def shape(self,source):return decode(self.native.shape_text(protocol.text(source)))

    def position(self,board,source,state='ready',count=0):
        names=['board','r_state_'+state,'r_last_none']
        names += [f'r_work_{i}_{c if c!="." else "empty"}' for i,c in enumerate(board)]
        names += [f'r_cell_{i}_{c if c!="." else "empty"}' for i,c in enumerate(board)]
        names += ['r_count_'+str(count)]
        return decode(self.injected.shape_text(''.join(self.codes[n] for n in names)+protocol.text(source)[1:]))

    def test_book_legality(self):
        self.assertEqual(len(self.book),8192)
        for board,move in self.book.items():self.assertIn(move,model.legal(board,True))

    def test_source_and_errors(self):
        for source in ('','b','bB4A3;','bA1A1;','bA5A4;','bB4A3;B4A3;','bgarbage','B','h',
                       'bB4','bB4A3','bB4A3Q;','bB4A3?;','b🙂','b\ue000',' b\n B4\tA3; ',
                       'bA0A1;','bF4A3;','bB4a3;'):
            with self.subTest(source=source):self.assertEqual(self.shape(source),self.expected(source))

    def test_opening_every_black_action(self):
        board,_,_,_=model.reply(model.INITIAL,book=self.book)
        legal=model.legal(board,False)
        for o in range(25):
            for t in range(25):
                key=model.square(o)+model.square(t)
                actual=self.position(board,key.upper()+';')
                if key not in legal:self.assertEqual(actual,(board,None,4),(board,key))
                else:
                    child=legal[key];clock=model.tick(board,key,0)
                    after,move,status,_=model.reply(child,clock,self.book)
                    self.assertEqual(actual,(after,None if move is None else move[2:4],STATUS[status]),key)

    def test_complete_random_games(self):
        rng=random.Random(20261022);outcomes=set();turns=0
        for game in range(12):
            source='b';board,move,status,count=model.reply(model.INITIAL,book=self.book)
            self.assertEqual(self.shape(source),self.expected(source))
            while status=='ready' and turns<2000:
                key=rng.choice(sorted(model.legal(board,False)))
                source+=key.upper()+';';count=model.tick(board,key,count)
                board,move,status,count=model.reply(model.legal(board,False)[key],count,self.book)
                self.assertEqual(self.shape(source),(board,None if move is None else move[2:4],STATUS[status]),source)
                turns+=1
            self.assertNotEqual(status,'ready',source)
            outcomes.add(status)
            self.assertEqual(self.shape(source+'bad🙂'),self.shape(source))
        print('Random complete games:',turns,'Black moves; outcomes',sorted(outcomes))

    def test_arbitrary_positions_and_promotions(self):
        rng=random.Random(1348);board=model.INITIAL;side=True;positions=[]
        for step in range(500):
            options=model.legal(board,side)
            if not options or model.dead(board):board=model.INITIAL;side=True;continue
            board=options[rng.choice(sorted(options))];side=not side
            if side:positions.append(board)
        for board in positions[::3]:
            after,move,status,_=model.reply(board,book=self.book)
            self.assertEqual(self.position(board,'b',state='header'),(after,None if move is None else move[2:4],STATUS[status]),board)
        # All four promotion choices are accepted; omitting the piece is not.
        board='K....'+'..p..'+'.....'+'.....'+'....k'
        for promotion in ('q','r','b','n'):
            key='c2c1'+promotion;child=model.legal(board,False)[key]
            after,move,status,_=model.reply(child,book=self.book)
            for count in (0,149):
                self.assertEqual(self.position(board,key.upper()+';',count=count),(after,None if move is None else move[2:4],STATUS[status]))
            if promotion in 'bn':self.assertEqual((after,move,status),(child,None,'draw'))
        self.assertEqual(self.position(board,'C2C1;'),(board,None,4))

    def test_pins_checks_and_captures(self):
        fixtures=[
            'K...R'+'.....'+'.....'+'....r'+'....k',
            'K....'+'.....'+'..k..'+'.....'+'.....',
            'K....'+'.....'+'...N.'+'....p'+'....k',
        ]
        for board in fixtures:
            keys={model.uci(move) for move in model.pseudo(board,False)}
            keys.update(('a1a1','e5d4','e4d4','c3b2'))
            options=model.legal(board,False)
            for key in keys:
                expected=(board,None,4)
                if key in options:
                    child=options[key];clock=model.tick(board,key,0)
                    after,move,status,_=model.reply(child,clock,self.book)
                    expected=after,None if move is None else move[2:4],STATUS[status]
                self.assertEqual(self.position(board,key.upper()+';'),expected,(board,key))

    def test_rule_clock_and_terminal_priority(self):
        # Find actual quiet moves in sampled boards so clock tests exercise
        # real movement, then compare the independent clock-aware reference.
        board='KQ......................k'
        for count in (148,149,150):
            after,move,status,_=model.reply(board,count,self.book)
            self.assertEqual(self.position(board,'b',state='header',count=count),(after,None if move is None else move[2:4],STATUS[status]))
        # Black's quiet 150th ply checkmates, taking precedence over the draw.
        board='K....'+'.....'+'.qk..'+'.....'+'.....'
        child=model.legal(board,False)['b3b2']
        self.assertEqual(self.position(board,'B3B2;',count=149),(child,None,3))
        # A checked king with no move is mate; an unchecked one is stalemate.
        for board,code in ((child,3),('K....'+'..q..'+'..k..'+'.....'+'.....',7)):
            self.assertEqual(self.position(board,'b',state='header'),(board,None,code))
        # A capture resets the counter before White chooses its response.
        board='K...Q'+'....r'+'.....'+'.....'+'....k';key='e2e1'
        after,move,status,_=model.reply(model.legal(board,False)[key],0,self.book)
        self.assertEqual(self.position(board,key.upper()+';',count=149),(after,None if move is None else move[2:4],STATUS[status]))

    def test_long_quiet_game_and_execution_budget(self):
        start='KR'+'.'*22+'k'
        board,move,status,count=model.reply(start);source='b';seen={board}
        while status=='ready':
            choices=[]
            for key,child in model.legal(board,False).items():
                after,last,st,clock=model.reply(child,model.tick(board,key,count))
                choices.append(((st=='ready',after in seen,st=='draw',key),key,after,last,st,clock))
            _,key,board,move,status,count=max(choices)
            source+=key.upper()+';';seen.add(board)
        self.assertEqual((status,count,len(source)),('draw',150,376))
        self.assertEqual(self.position(start,source,state='header'),(board,None,7))

    def test_metrics_and_transport(self):
        with TTFont(FONT) as font:
            self.assertEqual(font['head'].unitsPerEm,1000)
            self.assertEqual(font['OS/2'].fsType,0)
            self.assertNotIn(0xf0000,font.getBestCmap())
            self.assertNotIn('Google',font['name'].getDebugName(0))
            self.assertIn('Game Sans',font['name'].getDebugName(10))
            for code in STATUS.values():self.assertEqual(font['hmtx'].metrics['status_'+str(code)][0],code)
        self.assertEqual(self.shape('b'),self.shape(' b \n\t'))
        cases=['b','bB4A3;','🙂\ue000\0',' b\n\t']
        script="const {gardnerText}=require(process.argv[1]);process.stdout.write(JSON.stringify(JSON.parse(process.argv[2]).map(gardnerText)));"
        actual=json.loads(subprocess.check_output(['node','-e',script,str(FONT.with_name('controls.js').resolve()),json.dumps(cases)],text=True))
        self.assertEqual(actual,[protocol.text(s) for s in cases])


if __name__=='__main__':unittest.main()
