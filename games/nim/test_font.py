# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
from functools import lru_cache
from itertools import product
from pathlib import Path
import json
import random
import subprocess
import sys
import unittest

from fontTools.ttLib import TTFont
import model
from build import PASSES
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'shared'))
from native_font import NativeFont

FONT=Path(__file__).resolve().with_name('nim-font.ttf')


def independent_table(mode):
    table={}
    for a,b,c in product(range(32),repeat=3):
        if not(a or b or c):table[a,b,c]=mode=='M';continue
        children=[(x,b,c) for x in range(a)]+[(a,y,c) for y in range(b)]+[(a,b,z) for z in range(c)]
        table[a,b,c]=any(not table[child] for child in children)
    return table


class NimTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.native=NativeFont(FONT)
    @classmethod
    def tearDownClass(cls):cls.native.close()

    def decode(self,names):
        fields={}
        for heap in 'ABC':
            values=[n for n in names if n.startswith(f'r_{heap}_')]
            self.assertEqual(len(values),1,names);fields[heap]=int(values[0].rsplit('_',1)[1])
        mode=[n[-1] for n in names if n.startswith('r_mode_')]
        work=[int(n.rsplit('_',1)[1]) for n in names if n.startswith('r_work_')]
        lasts=[n for n in names if n.startswith('r_last_')]
        statuses=[n[7:] for n in names if n.startswith('status_')]
        self.assertEqual((len(mode),len(work),len(lasts),len(statuses)),(1,1,1,1),names)
        self.assertFalse(any(n.startswith(('p_','human_','ai_','set_')) for n in names),names)
        heaps=tuple(fields[h] for h in 'ABC')
        self.assertEqual(work[0],heaps[0]^heaps[1]^heaps[2])
        if lasts[0]=='r_last_none':last=None
        else:
            kind,heap,n=lasts[0].removeprefix('r_last_').split('_')
            last=kind,ord(heap)-65,int(n)
        return heaps,mode[0],last,statuses[0]

    def check_source(self,source,native=None):
        self.assertEqual(self.decode((native or self.native).shape(source)),model.replay(source),source)

    def test_complete_independent_strategy(self):
        for mode in 'NM':
            table=independent_table(mode)
            for heaps,value in table.items():
                self.assertEqual(model.winning(heaps,mode),value,(mode,heaps))
                move=model.choose(heaps,mode)
                if not any(heaps):self.assertIsNone(move);continue
                self.assertIsNotNone(move)
                child=model.apply(heaps,move)
                self.assertLess(sum(child),sum(heaps))
                if value:self.assertFalse(table[child],(mode,heaps,move))

    def test_every_compiled_initial_decision(self):
        for mode in 'NM':
            for a,b,c in product(range(32),repeat=3):
                self.check_source(f'b{mode}{a:02},{b:02},{c:02};')

    def test_full_clock_headers_and_move_amounts(self):
        for mode in 'NM':
            for n in range(32):
                for heap in range(3):
                    values=[0,0,0];values[heap]=n
                    header=f'h{mode}'+','.join(f'{x:02}' for x in values)+';'
                    self.check_source(header)
                    if n:self.check_source(header+'ABC'[heap]+f'{n:02};')
            for amount in range(1,32):
                for heap in 'ABC':
                    self.check_source(f'h{mode}31,31,31;{heap}{amount:02};')
                    self.check_source(f'h{mode}01,01,01;{heap}{amount:02};')
        rng=random.Random(420)
        for _ in range(300):
            heaps=tuple(rng.randrange(32) for _ in range(3));mode=rng.choice('NM');first=rng.choice('bh')
            self.check_source(first+mode+','.join(f'{n:02}' for n in heaps)+';')

    def test_complete_games_and_winning_invariant(self):
        rng=random.Random(910)
        for _ in range(150):
            mode=rng.choice('NM');heaps=tuple(rng.randrange(32) for _ in range(3))
            if not any(heaps):heaps=(1,0,0)
            first=rng.choice('bh');source=first+mode+','.join(f'{n:02}' for n in heaps)+';'
            font_winning=model.winning(heaps,mode) if first=='b' else not model.winning(heaps,mode)
            while True:
                self.check_source(source)
                current,_,last,status=model.replay(source)
                if status!='ready':
                    self.assertIn(status,('computer_won','human_won'))
                    if font_winning:self.assertEqual(status,'computer_won')
                    self.check_source(source+'A31;garbage🙂');break
                heap,amount=rng.choice(list(model.moves(current)))
                source+='ABC'[heap]+f'{amount:02};'

    def test_longest_history_both_rules(self):
        for mode in 'NM':
            @lru_cache(None)
            def longest(heaps):
                best=''
                for move in model.moves(heaps):
                    child=model.apply(heaps,move);suffix=''
                    if any(child):
                        child=model.apply(child,model.choose(child,mode))
                        if any(child):suffix=longest(child)
                    candidate='ABC'[move[0]]+f'{move[1]:02};'+suffix
                    if len(candidate)>len(best):best=candidate
                return best
            suffix,heaps=max(((longest(heaps),heaps) for heaps in product(range(32),repeat=3) if any(heaps)),
                             key=lambda item:(len(item[0]),item[1]))
            source='h'+mode+','.join(f'{n:02}' for n in heaps)+';'+suffix
            self.check_source(source)
            self.assertIn(model.replay(source)[3],('human_won','computer_won'))
            self.assertLessEqual(len(suffix)//4+1,PASSES)

    def test_misere_and_parser_boundaries(self):
        cases=('', 'b', 'bN', 'bM01,', 'bM01,02,', 'bN03,05,07', 'bX03,05,07;',
               'bN32,05,07;','bN03,32,07;','bN03,05,32;', 'hN01,00,00;A00;',
               'hN01,00,00;A02;','hM01,00,00;A01;','bM01,00,00;',
               'hN01,00,00;A01;','bN01,00,00;','bN00,00,00;','hM00,00,00;',
               'bM02,01,01;','bM02,01,00;','bM01,01,01;','bM01,01,00;',
               'bN03,05,06;','hM03,05,07;D01;','hM03,05,07;A1;',
               'hM03,05,07;A32;','hM03,05,07;A-1;','hN03,05,07;🙂',
               'hN03,05,07;\ue000',' b M 02 , 01 , 01 ;\nA 01 ;\t',
               'bM01,00,00;🙂A31;')
        for source in cases:self.check_source(source)
        self.assertEqual(model.replay('hM01,00,00;A01;')[3],'computer_won')
        self.assertEqual(model.replay('bM01,00,00;')[3],'human_won')

    def test_metrics_metadata_and_disabled_ligatures(self):
        args=['hb-shape',str(FONT),'--text='+model.START+model.DEFAULT+model.END,'--output-format=json']
        output=json.loads(subprocess.check_output(args,text=True));self.assertEqual(sum(g['ax'] for g in output),1801)
        output=json.loads(subprocess.check_output(args+['--features=-liga'],text=True))
        self.assertFalse(any(g['g'].startswith('status_') for g in output))
        with TTFont(FONT) as font:
            self.assertEqual(font['head'].unitsPerEm,1000);self.assertEqual(font['OS/2'].fsType,0)
            self.assertIn('COLR',font)


if __name__=='__main__':unittest.main()
