# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Build a complete, configurable Wythoff's Nim opponent in GSUB."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'shared'))
from fontgame import GameFont,group
from game_text import NAME_RECORDS, lettering, centered_lettering
from model import MAX_HEAP, cold

WIDTH, HEIGHT = 1800,1040
PASSES = MAX_HEAP+2
STATUS = {'ready':1,'computer_won':2,'human_won':3,'invalid':4,'malformed':5,'internal':6}
LABELS = ('Your turn','Font wins','You win','Invalid move','Check your input','Game error')


def coin(p,x,y,r=22):
    p.moveTo((x+r,y))
    p.qCurveTo((x+r,y+r),(x,y+r))
    p.qCurveTo((x-r,y+r),(x-r,y))
    p.qCurveTo((x-r,y-r),(x,y-r))
    p.qCurveTo((x+r,y-r),(x+r,y))
    p.closePath()


def build_font(output):
    f=GameFont('Wythoff Perfect Opponent',WIDTH,HEIGHT,name_records=NAME_RECORDS)
    raw=f.raw
    def frame(p,s):
        centered_lettering(p,"Wythoff's Nim",s+900,940,17)
        for i,heap in enumerate('AB'):
            lettering(p,'Heap '+heap,s+120+i*850,830,12)
    f.add('board',frame,advance=WIDTH,color=0,overlay=False)
    heaps={}
    for i,heap in enumerate('AB'):
        heaps[heap]=[]
        for n in range(MAX_HEAP+1):
            def draw(p,s,n=n,i=i):
                lettering(p,f'{n:02}',s+500+i*850,830,12)
                for token in range(n):
                    row,col=divmod(token,9)
                    coin(p,s+150+i*850+col*76,730-row*76)
            heaps[heap].append(f.add(f'r_{heap}_{n}',draw,color=1))
    cold_pairs=[(a,b) for a in range(MAX_HEAP+1) for b in range(MAX_HEAP+1) if cold(a,b)]
    partners={b:a for a,b in cold_pairs}
    differences=[f.add(f'r_diff_{n}') for n in range(2*MAX_HEAP+1)]
    actions={}
    for kind in 'AB':
        for n in range(MAX_HEAP+1):actions[kind,n]=f'Font left {n:02} in {kind}'
    for a,b in cold_pairs:actions['D',a,b]=f'Font left {a:02} and {b:02}'
    actions['take_A',1]='Font took 01 from A'
    ai={action:f.add('ai_'+'_'.join(map(str,action))) for action in actions}
    last=[f.add('r_last_none')]
    for action,label in actions.items():
        last.append(f.add('r_last_'+'_'.join(map(str,action)),
            lambda p,s,label=label:centered_lettering(p,label,s+900,130,10),color=3))
    for (status,code),label in zip(STATUS.items(),LABELS):
        f.add('status_'+status,lambda p,s,label=label:centered_lettering(p,label,s+900,50,11),advance=code,color=1 if code<4 else 2)
    numbers=[f.add(f'number_{n}') for n in range(MAX_HEAP+1)]
    states=['p_start','p_ai','p_human']
    for kind in 'bh':
        states += [f'p_{phase}_{kind}' for phase in ('A','comma','B','close')]
    for name in states:f.add(name)
    setters={heap:{kind:[f.add(f'set_{heap}_{kind}_{n}') for n in range(MAX_HEAP+1)]
                   for kind in 'bh'} for heap in 'AB'}
    events={'human':{kind:[None]+[f.add(f'human_{kind}_{n}') for n in range(1,MAX_HEAP+1)]
                     for kind in 'ABD'}}
    all_events={'human':[name for names in events['human'].values() for name in names[1:]],'ai':list(ai.values())}
    stages=[]
    def stage(name,rules,coverage,expose=None):
        f.lookup(name,rules,coverage,expose);stages.append(name)
    f.lookup('SPACE',[f'sub {raw[" "]} by NULL;'],[raw[' ']])
    f.lookup('NUMBER',[f'sub {raw[str(n//10)]} {raw[str(n%10)]} by {numbers[n]};' for n in range(MAX_HEAP+1)],
             [raw[str(n)] for n in range(7)])
    f.lookup('INIT',['sub begin by board r_A_0 r_B_0 r_diff_0 r_last_none p_start;'],['begin'])
    stage('BOOT',[f'sub p_start {raw[kind]} by p_A_{kind};' for kind in 'bh'],['p_start'])
    for heap in 'AB':
        values=[name for names in setters[heap].values() for name in names]
        stage('READ_'+heap,[f'sub p_{heap}_{kind} {numbers[n]} by {setters[heap][kind][n]};'
                            for kind in 'bh' for n in range(MAX_HEAP+1)],[f'p_{heap}_{k}' for k in 'bh'])
        stage('SET_'+heap,[f'sub {group(heaps[heap])}\' {group([setters[heap][k][n] for k in "bh"])} by {heaps[heap][n]};'
                           for n in range(MAX_HEAP+1)],heaps[heap],heaps[heap]+values)
        next_phase='comma' if heap=='A' else 'close'
        stage('NEXT_'+heap,[f'sub {group(setters[heap][k])} by p_{next_phase}_{k};' for k in 'bh'],values)
        if heap=='A':
            stage('COMMA',[f'sub p_comma_{k} {raw[","]} by p_B_{k};' for k in 'bh'],[f'p_comma_{k}' for k in 'bh'])
    stage('CLOSE',[f'sub p_close_{k} {raw[";"]} by '+('p_ai' if k=='b' else 'p_human')+';' for k in 'bh'],
          [f'p_close_{k}' for k in 'bh'])
    both=heaps['A']+heaps['B']
    stage('EMPTY',["sub r_A_0 r_B_0 [p_ai p_human]' by status_invalid;"],['p_ai','p_human'],both+['p_ai','p_human'])
    step=['sub p_human end by status_ready;']
    for kind in 'ABD':
        step += [f'sub p_human {raw[kind]} {numbers[n]} {raw[";"]} by {events["human"][kind][n]};' for n in range(1,MAX_HEAP+1)]
    bad=[*raw.values(),*numbers,'begin','.notdef']
    step.append(f'sub p_human {group(bad)} by status_malformed;')
    stage('STEP',step,['p_human'])
    for heap in 'AB':
        checks=[]
        for n in range(1,MAX_HEAP+1):
            checks.append(f'sub {group(heaps[heap][:n])} {group([events["human"][k][n] for k in (heap,"D")])}\' by status_invalid;')
        stage('CHECK_'+heap,checks,all_events['human'],heaps[heap]+all_events['human'])
    def apply_stage(player,heap):
        stage('APPLY_'+player+'_'+heap,[f'sub {group(heaps[heap][n:])}\' '
            +group([events[player][k][n] for k in (heap,'D')])+' by '+group(heaps[heap][:-n])+';'
            for n in range(1,MAX_HEAP+1)],heaps[heap],heaps[heap]+all_events[player])
    for heap in 'AB':apply_stage('human',heap)
    stage('H_TERMINAL',[f'sub r_A_0 r_B_0 {group(all_events["human"])}\' by status_human_won;'],all_events['human'],both+all_events['human'])
    stage('H_NEXT',[f'sub {group(all_events["human"])} by p_ai;'],all_events['human'])
    # An auxiliary register holds MAX_HEAP+B-A. Rebuilding it in two small
    # lookups avoids a table for every pair of heap sizes.
    stage('DIFF_BASE',[f'sub r_B_{b} {group(differences)}\' p_ai by r_diff_{MAX_HEAP+b};'
                       for b in range(MAX_HEAP+1)],differences,heaps['B']+differences+['p_ai'])
    stage('DIFF_SUB',[f'sub r_A_{a} {group(differences[a:])}\' p_ai by '
                      +group(differences[:len(differences)-a])+';'
                      for a in range(MAX_HEAP+1)],differences,heaps['A']+differences+['p_ai'])
    stage('CHOOSE_A',[f'sub {group(heaps["A"][target+1:])} r_B_{b} p_ai\' by {ai["A",target]};'
                       for b,target in partners.items() if target<MAX_HEAP],['p_ai'],both+['p_ai'])
    stage('CHOOSE_B',[f'sub r_A_{a} {group(heaps["B"][target+1:])} p_ai\' by {ai["B",target]};'
                       for a,target in partners.items() if target<MAX_HEAP],['p_ai'],both+['p_ai'])
    stage('CHOOSE_D',[f'sub {group(heaps["A"][a+1:])} r_diff_{MAX_HEAP+b-a} p_ai\' by {ai["D",a,b]};'
                       for a,b in cold_pairs if max(a,b)<MAX_HEAP],['p_ai'],heaps['A']+differences+['p_ai'])
    # Only nonempty cold positions reach this stage. Both heaps are positive,
    # and all moves lose, so removing one from A is an exact-outcome fallback.
    stage('FALLBACK',[f'sub p_ai by {ai["take_A",1]};'],['p_ai'])
    for i,heap in enumerate('AB'):
        updates=[]
        for target in range(MAX_HEAP+1):
            matching=[name for action,name in ai.items()
                      if (action[0]==heap and action[1]==target) or (action[0]=='D' and action[i+1]==target)]
            updates.append(f'sub {group(heaps[heap])}\' {group(matching)} by {heaps[heap][target]};')
        if heap=='A':updates.append(f'sub {group(heaps[heap][1:])}\' {ai["take_A",1]} by {group(heaps[heap][:-1])};')
        stage('APPLY_ai_'+heap,updates,heaps[heap],heaps[heap]+all_events['ai'])
    stage('LAST',[f'sub {group(last)}\' {name} by r_last_'+ '_'.join(map(str,action))+';'
                  for action,name in ai.items()],last,last+all_events['ai'])
    stage('AI_TERMINAL',[f'sub r_A_0 r_B_0 {group(all_events["ai"])}\' by status_computer_won;'],all_events['ai'],both+all_events['ai'])
    stage('AI_NEXT',[f'sub {group(all_events["ai"])} by p_human;'],all_events['ai'])
    residual=states+all_events['human']+all_events['ai']+[name for by_kind in setters.values() for names in by_kind.values() for name in names]
    f.lookup('FINAL',[f'sub {group(residual)} by status_malformed;'],residual)
    hidden=[*raw.values(),*numbers,'begin','end','.notdef']
    f.lookup('HIDE',[f'sub {group(hidden)} by hidden;'],hidden)
    return f.save(output,['SPACE','NUMBER','INIT'],stages,['FINAL','HIDE'],PASSES)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().with_name('wythoff-font.ttf'))
    build_font(parser.parse_args().output)


if __name__=='__main__':main()
