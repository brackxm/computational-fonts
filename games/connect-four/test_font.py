# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: GPL-3.0-only
"""Fresh and bundled GSUB vs an independent row-major reference model.

Public history tests use ONLY b and human digits. Register injection is confined
here to isolated transition/diagram tests; no such transport exists in the UI.
"""
import json
import random
import statistics
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable
from build import STATUS
from gsub import context_lookup, append_stage
from reference import (BRANCHES, DIAGRAMS, OPENINGS, board_of, choose,
                       drop, mirror, replay, transition, wins, won)
from shaping import Shaper

HERE = Path(__file__).resolve().parent


def diagnostic_font(original, output, abi, query=False):
    """Expose the actual bundled tables to controlled fixed-register queries."""
    f = TTFont(original)
    order = f.getGlyphOrder()
    cp = {n:0xf0000+i for i,n in enumerate(order)}
    cm = CmapSubtable.newSubtable(12); cm.platformID=3; cm.platEncID=10; cm.language=0
    cm.cmap={**f.getBestCmap(), **{v:k for k,v in cp.items()}}
    f['cmap'].tables.append(cm)
    if query:
        table = f['GSUB'].table; lookups = table.LookupList.Lookup
        indices=[]
        for stage in abi['stages']:
            records = [tuple(record) for i, record in enumerate(abi['records'])
                       if stage['start'] <= i < stage['end'] and
                       i >= abi['query_start'] and i != abi['dispatch_call']]
            if records:
                index, _ = append_stage(f, abi['slots'], records)
                indices.append(index)
        indices.append(len(lookups))
        parser = abi['slots'][abi['offsets']['parser']]
        lookups.append(context_lookup(f, [parser], [(0, abi['final'])]))
        liga=next(r.Feature for r in table.FeatureList.FeatureRecord if r.FeatureTag=='liga')
        liga.LookupListIndex=indices;liga.LookupCount=len(indices);table.LookupList.LookupCount=len(lookups)
    f.save(output)
    return cp


def tape(board, mode, parser='p_ready', last=4):
    names=['board']+[f'b_{x}_{y}_{board[y][x]}' for x in range(7) for y in range(6)]
    names+=['m_'+'_'.join(map(str,mode))]+[f'a_{x}_{y}_0' for x in range(7) for y in range(6)]
    names += [f'h_{x}_{next((y for y in range(6) if not board[y][x]),6)}' for x in range(7)]
    return names+[f'r_{x}_10' for x in range(7)]+['cnt_none','idle',f'last{last}',parser]


class ReferenceTests(unittest.TestCase):
    def test_optimized_python_keeps_board_updates(self):
        script = """
import json
from reference import board_of, replay
from verify_longest import opening_entries
jobs, _, states = opening_entries()
_, status, _, _, replies = replay('b135')
print(json.dumps([board_of('4'), status, replies, states, len(jobs)]))
"""
        result = json.loads(subprocess.check_output(
            [sys.executable, '-O', '-c', script], cwd=HERE, text=True, timeout=30))
        self.assertEqual(result, [board_of('4'), 'win', [5, 6, 7], 251, 1229])


class ConnectFourTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='connect-four-tests-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.directory=Path(cls.temp.name)
        cls.fresh=cls.directory/'nested/fresh.ttf'
        subprocess.run([sys.executable,str(HERE/'build.py'),'--output',str(cls.fresh)],
                       cwd=cls.directory,check=True,capture_output=True,timeout=240)
        cls.paths=[HERE/'connect-four-font.ttf',cls.fresh]
        cls.shapers=[Shaper(p) for p in cls.paths]
        cls.addClassCleanup(lambda:[s.close() for s in cls.shapers])
        cls.abi=json.loads((HERE/'connect-four-font.abi.json').read_text())
        cls.diagnostics=[]
        for i,path in enumerate(cls.paths):
            full=cls.directory/f'full{i}.ttf'; query=cls.directory/f'query{i}.ttf'
            cp=diagnostic_font(path,full,cls.abi)
            diagnostic_font(path,query,cls.abi,True)
            cls.diagnostics.append((Shaper(full),Shaper(query),cp))
        cls.addClassCleanup(lambda:[s.close() for a,b,c in cls.diagnostics for s in (a,b)])
        cls.times=[]

    def assert_board(self, output, board, status, last, mode=None):
        names=[g[0] for g in output]
        self.assertEqual([n for n in names if n.startswith('b_')],
                         [f'b_{x}_{y}_{board[y][x]}' for x in range(7) for y in range(6)])
        self.assertEqual([n for n in names if n.startswith('status_')],['status_'+status])
        self.assertEqual([n for n in names if n.startswith('last')],[f'last{last}'])
        if mode is not None:
            self.assertEqual([n for n in names if n.startswith('m_')],['m_'+'_'.join(map(str,mode))])
        self.assertEqual(names.count('board'),1)
        self.assertEqual(sum(g[1] for g in output),1000+STATUS[status])
        self.assertTrue(all(g[2:]==(0,0) for g in output))
        self.assertFalse(any(n.startswith(('event','p_','raw')) for n in names))
        self.assertEqual([n for n in names if n.startswith('h_')],
                         [f'h_{x}_{next((y for y in range(6) if not board[y][x]),6)}' for x in range(7)])

    def check(self, source, transport=False):
        board,status,last,mode,replies=replay(source)
        for shaper in self.shapers:
            start=time.perf_counter();output=shaper.run(source,transport=transport)
            self.times.append((len(source),time.perf_counter()-start))
            try: self.assert_board(output,board,status,last,mode)
            except AssertionError as e: raise AssertionError(f'{source}: {e}') from e
        return board,status,last,mode,replies

    def test_01_metadata_and_reproducibility(self):
        with TTFont(self.paths[0]) as a,TTFont(self.paths[1]) as b:
            for tag in ('GSUB','GDEF','glyf','hmtx','cmap','COLR','CPAL','name'):
                self.assertEqual(a[tag].compile(a),b[tag].compile(b),tag)
            self.assertEqual(a['name'].getDebugName(1),'Connect Four Perfect')
            self.assertIn('GPL-3.0',a['name'].getDebugName(13))
            for path in self.paths:
                with TTFont(path.with_suffix('.woff2')) as w,TTFont(path) as t:
                    for tag in ('GSUB','GDEF','glyf','hmtx','COLR','CPAL','cmap'):
                        self.assertEqual(w.getTableData(tag),t.getTableData(tag),(path,tag))
            self.assertEqual(a['OS/2'].fsType,0)
            self.assertEqual(a['COLR'].version,0)
            self.assertLess(len(a.getGlyphOrder()),3000)
            self.assertLess(len(a['GSUB'].table.LookupList.Lookup),4000)
            for who in (1,2): self.assertGreater(a['glyf'][f'b_3_0_{who}'].numberOfContours,0)
            for lookup in a['GSUB'].table.LookupList.Lookup:
                for sub in lookup.SubTable:
                    sub=getattr(sub,'ExtSubTable',sub)
                    if hasattr(sub,'GlyphCount'): self.assertLessEqual(sub.GlyphCount,64)

    def test_02_opening_transitions_both_orientations(self):
        counts={'legal':0,'full':0}
        for index,sequence in enumerate(OPENINGS):
            for flip in (0,1):
                before=board_of(sequence+BRANCHES[sequence])
                prior=int(BRANCHES[sequence])
                if flip: before=mirror(before);prior=8-prior
                for yellow in range(1,8):
                    board=[row[:] for row in before];mode=('branch',index,flip)
                    status,last='full',prior
                    target=mode
                    if drop(board,yellow-1,2) is not None:
                        target=transition(mode,yellow);red=choose(board,target)
                        self.assertIsNotNone(red)
                        self.assertIsNotNone(drop(board,red-1,1))
                        last=red;status='win' if won(board,1) else 'ready'
                        counts['legal']+=1
                    else: counts['full']+=1
                    for shaper,query,cp in self.diagnostics:
                        source=''.join(chr(cp[n]) for n in tape(before,mode,last=prior))+str(yellow)
                        self.assert_board(shaper.run(source),board,status,last,target)
        self.assertEqual(counts,{'legal':1822,'full':26})
        print('Opening edges:',counts,flush=True)

    def test_03_every_diagram_entry_board(self):
        count=0
        for sequence,index in BRANCHES.items():
            if not isinstance(index,int): continue
            for flip in (0,1):
                board=board_of(sequence)
                if flip: board=mirror(board)
                mode=('leaf',index,flip);red=choose(board,mode)
                expected=[row[:] for row in board];self.assertIsNotNone(drop(expected,red-1,1))
                status='win' if won(expected,1) else 'ready'
                for full,query,cp in self.diagnostics:
                    source=''.join(chr(cp[n]) for n in tape(board,mode,'event1'))
                    self.assert_board(query.run(source),expected,status,red,mode)
                count+=1
        self.assertEqual(count,1044)
        print('Oriented diagram entries:',count,flush=True)

    def test_04_human_only_games_every_prefix(self):
        rng=random.Random(0xc04)
        games=600
        reasons={'win':0,'block':0,'unique':0,'cancel':0}
        for game in range(games):
            source='b';board,status,last,mode,replies=self.check(source)
            while status=='ready':
                legal=[x for x in range(1,8) if not board[5][x-1]]
                if game<14: yellow=legal[0 if game%2==0 else -1]
                elif game<28: yellow=legal[min(game%7,len(legal)-1)]
                else: yellow=rng.choice(legal)
                after=[row[:] for row in board];drop(after,yellow-1,2)
                target=transition(mode,yellow)
                if wins(after,1): reasons['win']+=1
                elif wins(after,2): reasons['block']+=1
                elif target[0]=='leaf':
                    level_counts=[0]*10
                    for x in range(7):
                        y=next((n for n in range(6) if not after[n][x]),6)
                        if y<6: level_counts[int(DIAGRAMS[target[1]][5-y][6-x if target[2] else x])]+=1
                    selected=next(v for v,c in enumerate(level_counts) if c==1)
                    reasons['unique']+=1
                    if any(c>1 for c in level_counts[:selected]): reasons['cancel']+=1
                source+=str(yellow)
                board,status,last,mode,replies=self.check(source)
                self.assertIn(status,('ready','win'))
            self.assertEqual(status,'win')
        self.assertTrue(all(reasons.values()),reasons)
        print('Human-only games:',games,'policy cases:',reasons,flush=True)

    def test_05_errors_undo_reset_transport_and_disabled(self):
        for source in ('b','b1','b135','b1351','b135x','b0','b8','bb','b!','x','1b',' b','b 1',
                       'b11111111','b44444','b1234567','b\ue162','bλ','b🙂','b\n'):
            self.check(source,transport=True)
            if source.isascii() and '\n' not in source: self.check(source)
        for source in ('b135','b111','b44444'):
            for end in range(len(source),0,-1): self.check(source[:end])
            self.check('b')
        # Find/reject full columns from reachable nonterminal boards. Check that
        # the failed human drop does not alter the mode, board or last move.
        full_cases=0
        for column in '1234567':
            source='b'
            while replay(source)[1]=='ready':
                board,status,last,mode,replies=replay(source)
                full=[x for x in range(7) if board[5][x]]
                for x in full:
                    self.assertEqual(self.check(source+str(x+1))[1],'full');full_cases+=1
                if board[5][int(column)-1]: break
                source+=column
        self.assertGreater(full_cases,0)
        for shaper in self.shapers:
            for source in ('b','b135','b1111111'):
                result=shaper.run(source,enabled=False)
                self.assertFalse(any(g[0].startswith(('board','status_')) for g in result))
                self.assertNotIn(sum(g[1] for g in result),(1001,1002))

    def test_06_longest_reachable_history(self):
        proof=json.loads((HERE/'longest.json').read_text())
        source=proof['human_history']
        self.assertEqual(proof['maximum_plies'],1+2*(len(source)-1))
        for n in range(1,len(source)+1): self.check(source[:n])
        self.assertEqual(self.check(source)[1],'win')
        self.assertEqual(self.check(source+'7')[1],'trailing')
        for shaper in self.shapers:
            # Maximal malformed tail cannot restart or change a terminal board.
            self.assertEqual(shaper.run(source+'7'*200),shaper.run(source+'7'))
        adversarial=json.loads((HERE/'adversarial.json').read_text())
        prefixes={h[:n] for h in adversarial for n in range(1,len(h)+1)}
        for history in sorted(prefixes): self.check(history)
        self.assertTrue(all(replay(h)[1]=='win' for h in adversarial))
        print('Adversarial histories:',len(adversarial),'unique prefixes:',len(prefixes),flush=True)
        print('Longest reachable history:',proof,flush=True)

    def test_07_native_resource_lifetime(self):
        shaper = Shaper(self.paths[0])
        self.addCleanup(shaper.close)
        self.assertTrue(shaper.run('b'))
        shaper.close()
        shaper.close()
        with self.assertRaisesRegex(RuntimeError, 'closed font'):
            shaper.run('b')

    @classmethod
    def tearDownClass(cls):
        if not cls.times: return
        samples=[dt*1000 for length,dt in cls.times]
        report={'harfbuzz':cls.shapers[0].version,'history_shapes':len(cls.times),
                'median_ms':round(statistics.median(samples),4),'max_ms':round(max(samples),4)}
        longest=json.loads((HERE/'longest.json').read_text())['human_history']
        durations=[]
        for _ in range(100):
            start=time.perf_counter();cls.shapers[0].run(longest);durations.append((time.perf_counter()-start)*1000)
        report['longest_history_median_ms']=round(statistics.median(durations),4)
        print('MEASUREMENTS',json.dumps(report),flush=True)


if __name__=='__main__': unittest.main(verbosity=2)
