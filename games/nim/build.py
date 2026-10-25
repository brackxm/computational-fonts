# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Build normal and misère three-heap Nim with actual GSUB XOR arithmetic."""
import argparse
from itertools import product
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'shared'))
from fontgame import GameFont,group,rect
from game_text import NAME_RECORDS, lettering, centered_lettering
from model import MAX_HEAP

WIDTH,HEIGHT=1800,1150
PASSES=(3*MAX_HEAP+1)//2+2
STATUS={'ready':1,'computer_won':2,'human_won':3,'invalid':4,'malformed':5,'internal':6}


def binary(p,s,n,y):
    for bit in range(5):lettering(p,str((n>>(4-bit))&1),s+1250+bit*80,y,10)


def build_font(output):
    f=GameFont('Nim Perfect Opponent',WIDTH,HEIGHT,name_records=NAME_RECORDS);raw=f.raw
    def frame(p,s):
        for text,x in (('Heap',110),('Size',270),('Tokens',430),('Binary',1310)):
            lettering(p,text,s+x,920,8)
        for bit in range(5):lettering(p,str(1<<(4-bit)),s+1250+bit*80,880,7)
        for i,heap in enumerate('ABC'):lettering(p,heap,s+110,800-i*220,14)
        lettering(p,'XOR',s+110,230,8)
    f.add('board',frame,advance=WIDTH,color=0,overlay=False)
    modes={}
    for mode,title,rule in (('N','Normal Nim','Last token wins'),('M','Misère Nim','Last token loses')):
        def label(p,s,title=title,rule=rule):
            centered_lettering(p,title,s+900,1030,20);centered_lettering(p,rule,s+900,965,9)
        modes[mode]=f.add('r_mode_'+mode,label,color=0)
    heaps={}
    for i,heap in enumerate('ABC'):
        heaps[heap]=[]
        for n in range(MAX_HEAP+1):
            def draw(p,s,n=n,i=i):
                y=800-i*220
                lettering(p,f'{n:02}',s+270,y+10,12);binary(p,s,n,y+15)
                for token in range(n):
                    rect(p,s+430+token*24,y-10,10,85)
                    rect(p,s+428+token*24,y+60,14,15)
            heaps[heap].append(f.add(f'r_{heap}_{n}',draw,color=1))
    work=[]
    for n in range(MAX_HEAP+1):
        def draw(p,s,n=n):lettering(p,f'{n:02}',s+270,230,12);binary(p,s,n,235)
        work.append(f.add(f'r_work_{n}',draw,color=3))
    actions={('target',heap,n):f'Font left {n:02} in {heap}' for heap in 'ABC' for n in range(MAX_HEAP+1)}
    actions.update({('take',heap,1):f'Font took 01 from {heap}' for heap in 'ABC'})
    ai={action:f.add('ai_'+'_'.join(map(str,action))) for action in actions}
    lasts=[f.add('r_last_none')]
    for action,label in actions.items():
        lasts.append(f.add('r_last_'+'_'.join(map(str,action)),lambda p,s,label=label:centered_lettering(p,label,s+900,140,10),color=3))
    labels=('Your turn','Font wins','You win','Invalid move','Check your input','Game error')
    for (status,code),label in zip(STATUS.items(),labels):
        f.add('status_'+status,lambda p,s,label=label:centered_lettering(p,label,s+900,60,10),advance=code,color=1 if code<4 else 2)
    numbers=[f.add(f'number_{n}') for n in range(MAX_HEAP+1)]
    states=['p_start','p_ai','p_human']
    for first in 'bh':states += [f'p_{phase}_{first}' for phase in ('mode','A','comma_A','B','comma_B','C','close')]
    for name in states:f.add(name)
    mode_setters={(first,mode):f.add(f'set_mode_{first}_{mode}') for first in 'bh' for mode in 'NM'}
    setters={heap:{first:[f.add(f'set_{heap}_{first}_{n}') for n in range(MAX_HEAP+1)] for first in 'bh'} for heap in 'ABC'}
    human={heap:[None]+[f.add(f'human_{heap}_{n}') for n in range(1,MAX_HEAP+1)] for heap in 'ABC'}
    h_events=[name for names in human.values() for name in names[1:]];a_events=list(ai.values())
    stages=[]
    def stage(name,rules,coverage,expose=None):f.lookup(name,rules,coverage,expose);stages.append(name)
    f.lookup('SPACE',[f'sub {raw[" "]} by NULL;'],[raw[' ']])
    f.lookup('NUMBER',[f'sub {raw[str(n//10)]} {raw[str(n%10)]} by {numbers[n]};' for n in range(MAX_HEAP+1)],
             [raw[str(n)] for n in range(4)])
    initial=['board',modes['N'],*[heaps[h][0] for h in 'ABC'],work[0],'r_last_none','p_start']
    f.lookup('INIT',['sub begin by '+' '.join(initial)+';'],['begin'])
    stage('BOOT',[f'sub p_start {raw[k]} by p_mode_{k};' for k in 'bh'],['p_start'])
    stage('MODE',[f'sub p_mode_{k} {raw[m]} by {mode_setters[k,m]};' for k in 'bh' for m in 'NM'],[f'p_mode_{k}' for k in 'bh'])
    stage('SET_MODE',[f'sub {group(modes.values())}\' {group([mode_setters[k,m] for k in "bh"])} by {modes[m]};' for m in 'NM'],
          list(modes.values()),list(modes.values())+list(mode_setters.values()))
    stage('NEXT_MODE',[f'sub {group([mode_setters[k,m] for m in "NM"])} by p_A_{k};' for k in 'bh'],list(mode_setters.values()))
    for heap in 'ABC':
        values=[name for names in setters[heap].values() for name in names]
        stage('READ_'+heap,[f'sub p_{heap}_{k} {numbers[n]} by {setters[heap][k][n]};' for k in 'bh' for n in range(MAX_HEAP+1)],
              [f'p_{heap}_{k}' for k in 'bh'])
        stage('SET_'+heap,[f'sub {group(heaps[heap])}\' {group([setters[heap][k][n] for k in "bh"])} by {heaps[heap][n]};'
                           for n in range(MAX_HEAP+1)],heaps[heap],heaps[heap]+values)
        next_phase='close' if heap=='C' else 'comma_'+heap
        stage('NEXT_'+heap,[f'sub {group(setters[heap][k])} by p_{next_phase}_{k};' for k in 'bh'],values)
        if heap!='C':
            next_heap=chr(ord(heap)+1)
            stage('COMMA_'+heap,[f'sub p_comma_{heap}_{k} {raw[","]} by p_{next_heap}_{k};' for k in 'bh'],[f'p_comma_{heap}_{k}' for k in 'bh'])
    stage('CLOSE',[f'sub p_close_{k} {raw[";"]} by '+('p_ai' if k=='b' else 'p_human')+';' for k in 'bh'],[f'p_close_{k}' for k in 'bh'])
    all_heaps=[name for names in heaps.values() for name in names]
    stage('EMPTY',["sub r_A_0 r_B_0 r_C_0 [p_ai p_human]' by status_invalid;"],['p_ai','p_human'],all_heaps+['p_ai','p_human'])
    step=['sub p_human end by status_ready;']
    for heap in 'ABC':
        step += [f'sub p_human {raw[heap]} {numbers[n]} {raw[";"]} by {human[heap][n]};' for n in range(1,MAX_HEAP+1)]
    step.append(f'sub p_human {group([*raw.values(),*numbers,"begin",".notdef"])} by status_malformed;')
    stage('STEP',step,['p_human'])
    for heap in 'ABC':
        stage('CHECK_'+heap,[f'sub {group(heaps[heap][:n])} {human[heap][n]}\' by status_invalid;' for n in range(1,MAX_HEAP+1)],
              human[heap][1:],heaps[heap]+human[heap][1:])
    for heap in 'ABC':
        stage('APPLY_H_'+heap,[f'sub {group(heaps[heap][n:])}\' {human[heap][n]} by {group(heaps[heap][:-n])};' for n in range(1,MAX_HEAP+1)],
              heaps[heap],heaps[heap]+human[heap][1:])
    def terminal(name,events,normal,misere):
        stage(name,[f'sub {modes[m]} r_A_0 r_B_0 r_C_0 {group(events)}\' by status_{result};'
                     for m,result in (('N',normal),('M',misere))],events,list(modes.values())+all_heaps+events)
    terminal('H_TERMINAL',h_events,'human_won','computer_won')
    stage('H_NEXT',[f'sub {group(h_events)} by p_ai;'],h_events)
    special=[]
    for big in 'ABC':
        others=[h for h in 'ABC' if h!=big]
        for a,b in product(range(2),repeat=2):
            values={big:group(heaps[big][2:]),others[0]:heaps[others[0]][a],others[1]:heaps[others[1]][b]}
            target=1 if (a+b)%2==0 else 0
            special.append(f'sub {modes["M"]} '+' '.join(values[h] for h in 'ABC')+f' p_ai\' by {ai["target",big,target]};')
    for sizes in product(range(2),repeat=3):
        if not any(sizes):continue
        heap='ABC'[next(i for i,n in enumerate(sizes) if n)]
        special.append(f'sub {modes["M"]} '+' '.join(heaps[h][n] for h,n in zip('ABC',sizes))+f' p_ai\' by {ai["target",heap,0]};')
    stage('MISERE',special,['p_ai'],list(modes.values())+all_heaps+['p_ai'])
    stage('WORK_B',[f'sub r_B_{n} {group(work)}\' p_ai by {work[n]};' for n in range(MAX_HEAP+1)],work,heaps['B']+work+['p_ai'])
    def xor_stage(name,heap,clock=True):
        guard=' p_ai' if clock else ''
        rules=[f'sub {heaps[heap][n]} {group(work)}\'{guard} by {group([work[x^n] for x in range(MAX_HEAP+1)])};' for n in range(MAX_HEAP+1)]
        expose=heaps[heap]+work+(['p_ai'] if clock else [])
        if clock:stage(name,rules,work,expose)
        else:f.lookup(name,rules,work,expose)
    def choice(heap):
        stage('CHOOSE_'+heap,[f'sub {group(heaps[heap][n+1:])} {work[n]} p_ai\' by {ai["target",heap,n]};' for n in range(MAX_HEAP)],
              ['p_ai'],heaps[heap]+work+['p_ai'])
    xor_stage('XOR_C','C');choice('A')
    xor_stage('XOR_B','B');xor_stage('XOR_A','A');choice('B')
    # Reuse the same pure XOR tables to turn A^C into A^B.
    stages.extend(['XOR_C','XOR_B']);choice('C')
    for heap in 'ABC':
        stage('FALLBACK_'+heap,[f'sub {group(heaps[heap][1:])} p_ai\' by {ai["take",heap,1]};'],['p_ai'],heaps[heap]+['p_ai'])
    for heap in 'ABC':
        updates=[f'sub {group(heaps[heap])}\' {ai["target",heap,n]} by {heaps[heap][n]};' for n in range(MAX_HEAP+1)]
        updates.append(f'sub {group(heaps[heap][1:])}\' {ai["take",heap,1]} by {group(heaps[heap][:-1])};')
        stage('APPLY_AI_'+heap,updates,heaps[heap],heaps[heap]+a_events)
    stage('LAST',[f'sub {group(lasts)}\' {name} by r_last_'+'_'.join(map(str,action))+';' for action,name in ai.items()],lasts,lasts+a_events)
    terminal('AI_TERMINAL',a_events,'computer_won','human_won')
    stage('AI_NEXT',[f'sub {group(a_events)} by p_human;'],a_events)
    residual=states+h_events+a_events+list(mode_setters.values())+[name for d in setters.values() for names in d.values() for name in names]
    f.lookup('FINAL',[f'sub {group(residual)} by status_malformed;'],residual)
    f.lookup('TOTAL_B',[f'sub r_B_{n} {group(work)}\' by {work[n]};' for n in range(MAX_HEAP+1)],work,heaps['B']+work)
    xor_stage('TOTAL_C','C',False);xor_stage('TOTAL_A','A',False)
    hidden=[*raw.values(),*numbers,'begin','end','.notdef']
    f.lookup('HIDE',[f'sub {group(hidden)} by hidden;'],hidden)
    return f.save(output,['SPACE','NUMBER','INIT'],stages,['FINAL','TOTAL_B','TOTAL_C','TOTAL_A','HIDE'],PASSES,share_contours=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().with_name('nim-font.ttf'))
    build_font(parser.parse_args().output)


if __name__=='__main__':main()
