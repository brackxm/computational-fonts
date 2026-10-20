# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Build the complete solved 6x5 Cram game inside an OpenType font."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'shared'))
from fontgame import GameFont,group,rect
from game_text import NAME_RECORDS, lettering, centered_lettering
from model import COLS,ROWS,SIZE,MOVES,MIRROR,OPENING,SIDES

WIDTH,HEIGHT,CELL = 1800,1200,150
PASSES = SIZE//4+2
CODES = ('.','aL','aR','aT','aB','hL','hR','hT','hB')
STATUS = {'ready':1,'computer_won':2,'human_won':3,'invalid':4,'malformed':5,'internal':6}


def cell_xy(cell):
    row,col=divmod(cell,COLS)
    return 450+col*CELL,850-row*CELL


def build_font(output):
    f=GameFont('Cram Perfect Opponent',WIDTH,HEIGHT,name_records=NAME_RECORDS);raw=f.raw
    def frame(p,s):
        centered_lettering(p,'Cram / 6 by 5',s+900,1100,18)
        for col in range(COLS):lettering(p,chr(65+col),s+510+col*CELL,1030,9)
        for row in range(ROWS):lettering(p,str(row+1),s+385,915-row*CELL,9)
        for col in range(COLS+1):rect(p,s+450+col*CELL,250,2,ROWS*CELL)
        for row in range(ROWS+1):rect(p,s+450,250+row*CELL,COLS*CELL,2)
    f.add('board',frame,advance=WIDTH,color=0,overlay=False)
    registers=[]
    for cell in range(SIZE):
        variants=[]
        for code in CODES:
            def tile(p,s,cell=cell,code=code):
                if code=='.':return
                x,y=cell_xy(cell)
                shape={'L':(6,6,144,138),'R':(0,6,144,138),'T':(6,0,138,144),'B':(6,6,138,144)}[code[1]]
                dx,dy,w,h=shape;rect(p,s+x+dx,y+dy,w,h)
            variants.append(f.add(f'r_cell_{cell}_{"empty" if code=="." else code}',tile,color=1 if code[0]=='a' else 2))
        registers.append(variants)
    lasts=[f.add('r_last_none')]
    for key,cells in MOVES.items():
        def highlight(p,s,key=key,cells=cells):
            x,y=cell_xy(cells[0]);w,h=(300,150) if key[-1]=='H' else (150,300)
            if key[-1]=='V':y-=CELL
            for dx,dy,rw,rh in ((3,3,w-6,4),(3,h-7,w-6,4),(3,3,4,h-6),(w-7,3,4,h-6)):
                rect(p,s+x+dx,y+dy,rw,rh)
            centered_lettering(p,'Font: '+key,s+900,140,10)
        lasts.append(f.add('r_last_'+key,highlight,color=3))
    labels=('Your turn','Font wins','You win','Invalid move','Check your input','Game error')
    for (status,code),label in zip(STATUS.items(),labels):
        f.add('status_'+status,lambda p,s,label=label:centered_lettering(p,label,s+900,60,11),advance=code,color=1 if code<4 else 2)
    states=['p_start','p_human','p_evaluate']
    for name in states:f.add(name)
    events={player:{key:f.add(player+'_'+key) for key in MOVES} for player in ('human','ai')}
    all_regs=[name for names in registers for name in names]
    all_events={player:list(by_key.values()) for player,by_key in events.items()}
    stages=[]
    def stage(name,rules,coverage,expose=None):
        f.lookup(name,rules,coverage,expose);stages.append(name)
    f.lookup('SPACE',[f'sub {raw[" "]} by NULL;'],[raw[' ']])
    f.lookup('INIT',['sub begin by board '+' '.join(names[0] for names in registers)+' r_last_none p_start;'],['begin'])
    step=[f'sub p_start {raw["b"]} by {events["ai"][OPENING]};','sub p_human end by status_ready;']
    for col in 'ABCDEF':
        for row in '12345':
            for orientation in 'HV':
                key=col+row+orientation
                result=events['human'].get(key,'status_invalid')
                step.append(f'sub p_human {raw[col]} {raw[row]} {raw[orientation]} by {result};')
    for state,allowed in (('p_start',raw['b']),('p_human','end')):
        bad=[*raw.values(),'begin','end','.notdef'];bad.remove(allowed)
        step.append(f'sub {state} {group(bad)} by status_malformed;')
    stage('STEP',step,['p_start','p_human'])
    # All cell slots stay in a fixed order. Full context patterns allow each
    # validation/application phase to use ONE lookup, without a scan per cell.
    def pattern(forced):
        return ' '.join(group(forced.get(i,names)) for i,names in enumerate(registers))
    parts={cell:{side:[] for side in 'LRTB'} for cell in range(SIZE)}
    for key,cells in MOVES.items():
        for cell,side in zip(cells,SIDES[key[-1]]):parts[cell][side].append(key)
    for player in ('human','ai'):
        checks=[];updates=[]
        for cell,names in enumerate(registers):
            containing=[events[player][key] for keys in parts[cell].values() for key in keys]
            checks.append(f'sub {pattern({cell:names[1:]})} {group(containing)}\' by status_'+('invalid' if player=='human' else 'internal')+';')
            for side,keys in parts[cell].items():
                matching=[events[player][key] for key in keys]
                if matching:
                    tail=' '.join(group(n) for n in registers[cell+1:])
                    dest=names[CODES.index(('h' if player=='human' else 'a')+side)]
                    updates.append(f'sub {names[0]}\' {tail} {group(matching)} by {dest};')
        stage('CHECK_'+player,checks,all_events[player],all_regs+all_events[player])
        stage('APPLY_'+player,updates,[names[0] for names in registers],all_regs+all_events[player])
        if player=='human':stage('MIRROR',[f'sub {events[player][key]} by {events["ai"][MIRROR[key]]};' for key in MOVES],all_events[player])
    stage('LAST',[f'sub {group(lasts)}\' {events["ai"][key]} by r_last_{key};' for key in MOVES],lasts,lasts+all_events['ai'])
    stage('EVALUATE',[f'sub {group(all_events["ai"])} by p_evaluate;'],all_events['ai'])
    stage('AVAILABLE',[f'sub {pattern({a:[registers[a][0]],b:[registers[b][0]]})} p_evaluate\' by p_human;'
                        for a,b in MOVES.values()],['p_evaluate'],all_regs+['p_evaluate'])
    stage('WIN',['sub p_evaluate by status_computer_won;'],['p_evaluate'])
    residual=states+all_events['human']+all_events['ai']
    f.lookup('FINAL',[f'sub {group(residual)} by status_malformed;'],residual)
    hidden=[*raw.values(),'begin','end','.notdef']
    f.lookup('HIDE',[f'sub {group(hidden)} by hidden;'],hidden)
    return f.save(output,['SPACE','INIT'],stages,['FINAL','HIDE'],PASSES)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().with_name('cram-font.ttf'))
    build_font(parser.parse_args().output)


if __name__=='__main__':main()
