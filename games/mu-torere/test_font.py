# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
from collections import Counter
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

FONT=Path(__file__).resolve().with_name('mu-torere-font.ttf')


def independent_solution():
    """Relative bitboard fixed point, separate from the color/queue solver."""
    graph={}
    for own in range(1<<9):
        if own.bit_count()!=4:continue
        for blank in range(9):
            if own>>blank&1:continue
            enemy=511^own^(1<<blank)
            children=[]
            for origin in range(9):
                if not own>>origin&1:continue
                if origin==8:allowed=blank!=8
                elif blank==8:
                    adjacent=(1<<((origin+7)%8))|(1<<((origin+1)%8))
                    allowed=bool(enemy&adjacent)
                else:allowed=abs(origin-blank) in (1,7)
                if allowed:children.append((enemy,origin))
            graph[own,blank]=children
    values={node:-1 for node,children in graph.items() if not children}
    while True:
        changed={}
        for node,children in graph.items():
            if node in values:continue
            if any(values.get(child)==-1 for child in children):changed[node]=1
            elif all(values.get(child)==1 for child in children):changed[node]=-1
        if not changed:break
        values.update(changed)
    return graph,{node:values.get(node,0) for node in graph}


class MuTorereTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.native=NativeFont(FONT)
    @classmethod
    def tearDownClass(cls):cls.native.close()

    def decode(self,names):
        states=[n for n in names if n.startswith('r_') and not n.startswith('r_last_')]
        lasts=[n for n in names if n.startswith('r_last_')]
        statuses=[n[7:] for n in names if n.startswith('status_')]
        self.assertEqual(len(states),1,names)
        self.assertEqual(len(lasts),1,names)
        self.assertEqual(len(statuses),1,names)
        self.assertEqual(len(names),4,names)  # No stale board, cursor, or raw input.
        position=model.INITIAL if states[0]=='r_header' else model.POSITIONS[int(states[0].rsplit('_',1)[1])]
        last=None if lasts[0]=='r_last_none' else tuple(map(int,lasts[0].split('_')[-2:]))
        return position,last,statuses[0]

    def shape(self,source):return self.decode(self.native.shape(source))
    def check_source(self,source):self.assertEqual(self.shape(source),model.replay(source),source)

    def test_independent_complete_solution(self):
        graph,reference=independent_solution()
        values,distance=model.solve()
        self.assertEqual(len(graph),630)
        for position in model.POSITIONS:
            blank=position.index('.')
            for player in 'ha':
                own=sum(1<<i for i,c in enumerate(position) if c==player)
                node=(position,player)
                self.assertEqual(values[node],reference[own,blank],node)
                options=model.moves(position,player)
                self.assertEqual(set(options),{child[1] for child in graph[own,blank]},node)
                enemy=511^own^(1<<blank)
                for origin,child in options.items():
                    next_own=sum(1<<i for i,c in enumerate(child) if c==model.opponent(player))
                    self.assertEqual((next_own,child.index('.')),(enemy,origin))
                child_values=[values[child,model.opponent(player)] for child in options.values()]
                if not options:self.assertEqual((values[node],distance[node]),(-1,0))
                elif values[node]==1:
                    ranks=[distance[child,model.opponent(player)] for child in options.values()
                           if values[child,model.opponent(player)]==-1]
                    self.assertEqual(distance[node],1+min(ranks))
                elif values[node]==-1:
                    self.assertTrue(all(v==1 for v in child_values))
                    self.assertEqual(distance[node],1+max(distance[c,model.opponent(player)] for c in options.values()))
                else:
                    self.assertIn(0,child_values)
                    self.assertNotIn(-1,child_values)
                move=model.choose(position,player)
                if move is not None:
                    self.assertEqual(values[options[move],model.opponent(player)],-values[node])
        pending=[(model.INITIAL,'h')];seen=set(pending)
        while pending:
            position,player=pending.pop()
            for child in model.moves(position,player).values():
                node=child,model.opponent(player)
                if node not in seen:seen.add(node);pending.append(node)
        self.assertEqual(len(seen),1180)
        self.assertEqual(Counter(values[node] for node in seen),Counter({1:208,-1:128,0:844}))

    def test_every_compiled_transition(self):
        # Trusted test-only cmap aliases expose the already compiled cursor
        # states. None of these aliases are shipped in the bundled font.
        with TTFont(FONT) as font:
            codes={name:chr(0xf0000+i) for i,name in enumerate(font.getGlyphOrder())}
            cmap=CmapSubtable.newSubtable(12)
            cmap.platformID,cmap.platEncID,cmap.language=3,10,0
            cmap.cmap=dict(font.getBestCmap())
            cmap.cmap.update({ord(c):name for name,c in codes.items()})
            font['cmap'].tables.append(cmap)
            with tempfile.TemporaryDirectory() as temp:
                path=Path(temp)/'test.ttf';font.save(path)
                native=NativeFont(path)
                try:
                    def run(state,source):
                        text=codes['board']+codes[state]+codes['r_last_none']+transport(source)[1:]
                        return self.decode(native.shape_text(text))
                    values,_=model.solve()
                    for position in model.POSITIONS:
                        if not model.moves(position,'h'):continue
                        state=f'r_active_{model.IDS[position]}'
                        for token in '123456789=x':
                            expected=(position,None,'malformed')
                            if token=='=':expected=(position,None,'draw' if values[position,'h']>=0 else 'invalid')
                            elif token in '123456789':
                                origin=int(token)-1;options=model.moves(position,'h')
                                expected=model.reply(options[origin]) if origin in options else (position,None,'invalid')
                            self.assertEqual(run(state,token),expected,(position,token))
                    for name in codes:
                        if name.startswith(('r_invalid_','r_malformed_','r_draw_','r_computer_won_','r_human_won_')):
                            status=name[2:].rsplit('_',1)[0];index=int(name.rsplit('_',1)[1])
                            self.assertEqual(run(name,'h9=bad'*3),(model.POSITIONS[index],None,status),name)
                finally:native.close()

    def test_all_policy_reachable_games(self):
        pending=list('hbwl');seen=set();terminals=set()
        while pending:
            source=pending.pop();position,last,status=model.replay(source)
            self.check_source(source)
            if status!='ready':
                terminals.add(status);self.check_source(source+'9=invalid🙂');continue
            if position in seen:continue
            seen.add(position)
            self.check_source(source+'=')
            for origin in range(9):
                child=source+str(origin+1)
                self.check_source(child)
                if origin in model.moves(position,'h'):pending.append(child)
        self.assertIn('computer_won',terminals)
        self.assertIn('human_won',terminals)
        self.assertGreater(len(seen),20)

    def test_long_cycles_and_terminal_freezing(self):
        prefix,cycle='h194289','175328649'
        self.assertEqual(model.replay(prefix),model.replay(prefix+cycle))
        source=prefix+cycle*1200  # 10,806 human moves; no fixed shaping clock.
        self.check_source(source)
        self.assertEqual(self.shape(source)[2],'ready')
        self.check_source(source+'=')
        self.check_source('h='+'uninterpreted🙂'*1000)
        self.check_source('w817'+'123456789'*1000)

    def test_parser_centre_rule_and_presets(self):
        for source in ('','h','b','h1','h4','h2','h3','b1','b4','h9','h=','b=','w817','l91','l=',
                       'H','bad','h0','h10','h!','h\ue000','h🙂','h\0',' h\n1\t9 4\r2 8 9 '):
            self.check_source(source)
        self.assertEqual(model.replay('h2')[2],'invalid')
        self.assertEqual(model.replay('h3')[2],'invalid')
        self.assertEqual(model.replay('w817')[2],'human_won')
        self.assertEqual(model.replay('l91')[2],'computer_won')

    def test_metrics_metadata_and_disabled_ligatures(self):
        args=['hb-shape',str(FONT),'--text='+model.START+'h'+model.END,'--output-format=json']
        output=json.loads(subprocess.check_output(args,text=True))
        self.assertEqual(sum(g['ax'] for g in output),1801)
        output=json.loads(subprocess.check_output(args+['--features=-liga'],text=True))
        self.assertFalse(any(g['g'].startswith('status_') for g in output))
        with TTFont(FONT) as font:
            self.assertEqual(font['head'].unitsPerEm,1000)
            self.assertEqual(font['OS/2'].fsType,0)
            self.assertIn('COLR',font)


if __name__=='__main__':unittest.main()
