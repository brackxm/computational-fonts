# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
import json
from functools import lru_cache
from pathlib import Path
import random
import subprocess
import sys
import unittest

from fontTools.ttLib import TTFont
import model
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'shared'))
from native_font import NativeFont

HERE=Path(__file__).resolve().parent
FONT=HERE/'wythoff-font.ttf'


def solve(limit):
    table={}
    for a in range(limit+1):
        for b in range(limit+1):
            children=[(x,b) for x in range(a)]+[(a,y) for y in range(b)]
            children += [(a-k,b-k) for k in range(1,min(a,b)+1)]
            table[a,b]=any(not table[child] for child in children)
    return table


class WythoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.native=NativeFont(FONT)
    @classmethod
    def tearDownClass(cls):cls.native.close()

    def shape(self,source):
        names=self.native.shape(source)
        heaps=tuple(int(next(n for n in names if n.startswith(f'r_{heap}_')).rsplit('_',1)[1]) for heap in 'AB')
        last=next(n for n in names if n.startswith('r_last_'))
        if last=='r_last_none':last=None
        elif last=='r_last_take_A_1':last=('take_A',1)
        else:
            fields=last.removeprefix('r_last_').split('_')
            last=(fields[0],*map(int,fields[1:]))
        statuses=[n[7:] for n in names if n.startswith('status_')]
        self.assertEqual(len(statuses),1,(source,names))
        return heaps,last,statuses[0]

    def check_source(self,source):self.assertEqual(self.shape(source),model.replay(source),source)

    def test_exact_integer_strategy(self):
        for move in (('',1),('AB',1),('A',0),('A',1.5),('D',64)):
            with self.assertRaises(ValueError):model.apply((63,63),move)
        table=solve(model.MAX_HEAP)
        for heaps,winning in table.items():
            self.assertEqual(winning,not model.cold(*heaps),heaps)
            move=model.choose(heaps)
            if heaps==(0,0):self.assertIsNone(move);continue
            child=model.apply(heaps,move)
            self.assertGreaterEqual(min(child),0)
            self.assertLess(sum(child),sum(heaps))
            if winning:self.assertFalse(table[child],(heaps,move))
        # Check the integer formula far beyond the font's bounded state space
        # against the independent greedy mex construction, with no floats.
        used=set()
        a=0
        for n in range(10000):
            while a in used:a+=1
            b=a+n
            self.assertTrue(model.cold(a,b))
            used.update((a,b))

    def test_every_initial_position_native(self):
        for a in range(model.MAX_HEAP+1):
            for b in range(model.MAX_HEAP+1):
                for first in 'bh':self.check_source(f'{first}{a:02},{b:02};')

    def test_move_amounts_and_errors(self):
        for n in range(1,model.MAX_HEAP+1):
            for first in ('h63,63;','h00,63;','h63,00;','h01,02;'):
                for kind in 'ABD':self.check_source(first+f'{kind}{n:02};')
        for source in ('','b','b31','b31,','b31,47','h00,00;','h64,10;','h10,64;',
                       'h1,02;','H01,02;','h01,02;A00;','h01,02;A64;','h01,02;A1;',
                       'h01,02;A01','h01,02;A-1;','h01,02;X01;','h01,02;🙂',
                       'b31,47;A01;B01;',' b 31 , 47 ; \n A 01 ;\t','h01,01;D01;garbage🙂',
                       'b01,01;garbage🙂','b31,47;\ue000','h01,02;A01;;'):
            self.check_source(source)

    def test_complete_games(self):
        rng=random.Random(812)
        for _ in range(200):
            a,b=rng.randrange(64),rng.randrange(64)
            if not(a or b):b=1
            source=f'{rng.choice("bh")}{a:02},{b:02};'
            while True:
                self.check_source(source)
                heaps,last,status=model.replay(source)
                if status!='ready':
                    self.assertIn(status,('human_won','computer_won'))
                    break
                kind,n=rng.choice(list(model.moves(*heaps)))
                source+=f'{kind}{n:02};'

    def test_longest_legal_history(self):
        @lru_cache(None)
        def longest(heaps):
            best=''
            for move in model.moves(*heaps):
                child=model.apply(heaps,move)
                suffix=''
                if child!=(0,0):
                    child=model.apply(child,model.choose(child))
                    if child!=(0,0):suffix=longest(child)
                candidate=f'{move[0]}{move[1]:02};'+suffix
                if len(candidate)>len(best):best=candidate
            return best
        candidates=[(longest((a,b)),a,b) for a in range(64) for b in range(64) if a or b]
        suffix,a,b=max(candidates,key=lambda item:(len(item[0]),item[1:]))
        source=f'h{a:02},{b:02};'+suffix
        self.check_source(source)
        self.assertIn(self.shape(source)[2],('human_won','computer_won'))
        self.check_source(source+'unsupported🙂')

    def test_ligatures_metrics_and_metadata(self):
        text=model.START+model.DEFAULT+model.END
        args=['hb-shape',str(FONT),'--text='+text,'--output-format=json']
        out=json.loads(subprocess.check_output(args,text=True))
        self.assertEqual(sum(g['ax'] for g in out),1801)
        out=json.loads(subprocess.check_output(args+['--features=-liga'],text=True))
        self.assertFalse(any(g['g'].startswith('status_') for g in out))
        with TTFont(FONT) as font:
            self.assertEqual(font['head'].unitsPerEm,1000)
            self.assertEqual(font['OS/2'].fsType,0)
            self.assertIn('COLR',font)


if __name__=='__main__':unittest.main()
