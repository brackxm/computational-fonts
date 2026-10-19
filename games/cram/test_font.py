# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import json
import subprocess
import sys
import unittest

from fontTools.ttLib import TTFont
import model
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'shared'))
from native_font import NativeFont

FONT=Path(__file__).resolve().with_name('cram-font.ttf')


class CramTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.native=NativeFont(FONT)
    @classmethod
    def tearDownClass(cls):cls.native.close()

    def shape(self,source):
        names=self.native.shape(source)
        cells={int(n.split('_')[2]):n.split('_')[3] for n in names if n.startswith('r_cell_')}
        self.assertEqual(set(cells),set(range(30)),source)
        cells=tuple('.' if cells[i]=='empty' else cells[i] for i in range(30))
        lasts=[n.removeprefix('r_last_') for n in names if n.startswith('r_last_')]
        statuses=[n[7:] for n in names if n.startswith('status_')]
        self.assertEqual(len(lasts),1,source);self.assertEqual(len(statuses),1,source)
        return cells,None if lasts[0]=='none' else lasts[0],statuses[0]

    def check_source(self,source):self.assertEqual(self.shape(source),model.replay(source),source)

    def test_independent_symmetry_proof(self):
        # Independent coordinate construction, not the builder's move table.
        pairs=[]
        for y in range(5):
            for x in range(6):
                for xx,yy in ((x+1,y),(x,y+1)):
                    if xx<6 and yy<5:pairs.append(((x,y),(xx,yy)))
        self.assertEqual(len(pairs),49)
        for pair in pairs:
            indices=tuple(sorted(y*6+x for x,y in pair))
            self.assertIn(indices,model.BY_CELLS)
            reflected=tuple(sorted((4-y)*6+5-x for x,y in pair))
            key=model.BY_CELLS[indices]
            self.assertEqual(model.MOVES[model.MIRROR[key]],reflected)
        center={(2,2),(3,2)}
        for bits in range(1<<14):
            occupied=set(center)
            for i in range(14):
                if bits>>i&1:
                    y,x=divmod(i,6)
                    occupied.update(((x,y),(5-x,4-y)))
            for pair in pairs:
                move=set(pair)
                if move&occupied:continue
                reply={(5-x,4-y) for x,y in move}
                self.assertFalse(reply&occupied)
                self.assertFalse(reply&move)
                child=occupied|move|reply
                self.assertEqual(child,{(5-x,4-y) for x,y in child})

    def test_every_reachable_position_and_legal_reply(self):
        initial=sum(1<<i for i in model.MOVES[model.OPENING])
        sources={initial:'b'};pending=[initial];edges=0;terminals=0
        while pending:
            mask=pending.pop();source=sources[mask]
            cells,last,status=model.replay(source)
            self.check_source(source)
            legal=model.available(cells)
            if not legal:
                terminals+=1;self.assertEqual(status,'computer_won')
                self.check_source(source+'A1Hbroken🙂')
                continue
            self.assertEqual(status,'ready')
            self.check_source(source+'C3H')  # Opening is always occupied.
            for key in legal:
                edges+=1
                child_source=source+key
                self.check_source(child_source)
                child,_,child_status=model.replay(child_source)
                self.assertNotEqual(child_status,'internal')
                child_mask=sum(1<<i for i,c in enumerate(child) if c!='.')
                if child_mask not in sources:sources[child_mask]=child_source;pending.append(child_mask)
        self.assertEqual(len(sources),2104)
        self.assertEqual(edges,20392)
        self.assertEqual(terminals,89)
        longest=max(sources.values(),key=len)
        self.assertEqual(len(longest),22)  # Opening plus seven human turns.
        self.check_source(longest)

    def test_parser_and_boundaries(self):
        for col in 'ABCDEF':
            for row in '12345':
                for direction in 'HV':self.check_source('b'+col+row+direction)
        for source in ('','B','bb','bA1','bA','bG1H','bA6H','bA1h','bA0H','bA1H;',
                       'bA1HA1H','bA1HE5H',' b\nA1 H\tA2 V ','b🙂','b\ue000','b\0'):
            self.check_source(source)

    def test_metrics_metadata_and_disabled_ligatures(self):
        args=['hb-shape',str(FONT),'--text='+model.START+'b'+model.END,'--output-format=json']
        out=json.loads(subprocess.check_output(args,text=True))
        self.assertEqual(sum(g['ax'] for g in out),1801)
        out=json.loads(subprocess.check_output(args+['--features=-liga'],text=True))
        self.assertFalse(any(g['g'].startswith('status_') for g in out))
        with TTFont(FONT) as font:
            self.assertEqual(font['head'].unitsPerEm,1000)
            self.assertEqual(font['OS/2'].fsType,0)
            self.assertIn('COLR',font)


if __name__=='__main__':unittest.main()
