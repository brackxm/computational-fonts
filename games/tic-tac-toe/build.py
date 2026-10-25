# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Compile standard tic-tac-toe with a complete perfect opponent for either side."""
import argparse
from collections import defaultdict
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'shared'))
from fontgame import GameFont,group,rect,circle,components
from game_text import NAME_RECORDS, lettering, centered_lettering
import model

WIDTH,HEIGHT,CELL=1800,1250,240
STATUS={'ready':1,'computer_won':2,'human_won':3,'invalid':4,'malformed':5,'internal':6,'draw':7}


def cell_xy(index):return 540+(index%3)*CELL,780-(index//3)*CELL


def positions():
    boards={model.INITIAL}
    for board,human in model.policy_graph():
        boards.add(board)
        boards.update(model.reply(child,human)[0] for child in model.moves(board,human).values())
    return tuple(sorted(boards))


def build_font(output):
    f=GameFont('Tic Tac Toe Perfect Opponent',WIDTH,HEIGHT,name_records=NAME_RECORDS);raw=f.raw
    def frame(p,s):
        centered_lettering(p,'Tic-tac-toe',s+900,1130,20)
        for i in (1,2):
            rect(p,s+540+i*CELL-3,300,6,3*CELL)
            rect(p,s+540,300+i*CELL-3,3*CELL,6)
        for i in range(9):
            x,y=cell_xy(i);lettering(p,str(i+1),s+x+13,y+15,7)
    f.add('board',frame,advance=WIDTH,overlay=False)
    sprites={}
    for side in 'xo':
        for point in range(9):
            def mark(p,s,side=side,point=point):
                x,y=cell_xy(point);x+=s+CELL//2;y+=CELL//2
                if side=='o':circle(p,x,y,65);circle(p,x,y,49,True)
                else:
                    for direction in (-1,1):
                        points=[(x-61,y+direction*-49),(x-49,y+direction*-61),
                                (x+61,y+direction*49),(x+49,y+direction*61)]
                        if direction<0:points.reverse()
                        p.moveTo(points[0])
                        for point in points[1:]:p.lineTo(point)
                        p.closePath()
            sprites[side,point]=f.add(f'mark_{side}_{point}',mark)
    boards=positions();ids={board:i for i,board in enumerate(boards)};paints={};painted={}
    for board in boards:
        layers=[]
        for side,color in (('x',2),('o',1)):
            points=tuple(i for i,c in enumerate(board) if c==side)
            if (side,points) not in painted:
                mask=sum(1<<i for i in points)
                painted[side,points]=f.add(f'paint_{side}_{mask}',components(sprites[side,i] for i in points))
            layers.append((painted[side,points],color))
        paints[board]=layers
    for human,text in (('x','You: X    Font: O'),('o','You: O    Font: X')):
        f.add('role_'+human,lambda p,s,text=text:centered_lettering(p,text,s+900,205,9))
    for value,text in ((0,'Draw with perfect play'),(-1,'Font can force a win')):
        f.add('hint_'+str(value).replace('-','m'),lambda p,s,text=text:centered_lettering(p,text,s+900,140,8))
    def state(name,board,human,hint=None):
        layers=paints[board]+[('role_'+human,0)]
        if hint is not None:
            hint_name='hint_'+str(hint).replace('-','m');layers.append((hint_name,0))
        return f.layered(name,layers)
    active={(board,human):state(f'r_active_{human}_{ids[board]}',board,human,model.solve(board,human)[0])
            for board,human in model.policy_graph()}
    stopped={}
    def stop(board,human,status):
        key=board,human,status
        if key not in stopped:stopped[key]=state(f'r_{status}_{human}_{ids[board]}',board,human)
        return stopped[key]
    header=state('r_header',model.INITIAL,'x')
    lasts=[f.add('r_last_none')];last_names={}
    for key in '123456789':
        def highlight(p,s,key=key):
            x,y=cell_xy(int(key)-1)
            for dx,dy,w,h in ((6,6,CELL-12,5),(6,CELL-11,CELL-12,5),(6,6,5,CELL-12),(CELL-11,6,5,CELL-12)):
                rect(p,s+x+dx,y+dy,w,h)
            centered_lettering(p,'Font played '+key,s+900,75,9)
        name=f.add('r_last_'+key,highlight,color=3);lasts.append(name);last_names[key]=name
    for status,label in (('ready','Your turn'),('computer_won','Font wins'),('human_won','You win'),
                         ('invalid','Occupied square'),('malformed','Check your input'),('internal','Game error'),('draw','Draw')):
        f.add('status_'+status,lambda p,s,label=label:centered_lettering(p,label,s+900,10,10),
              advance=STATUS[status],color=1 if status in ('ready','draw','computer_won','human_won') else 2)
    def cursor(board,last,status,human):
        names=[active[board,human] if status=='ready' else stop(board,human,status)]
        if last is not None:names.append(last_names[last])
        return ' '.join(names)
    rules=[f'sub {header} {raw["h"]}\' by {active[model.INITIAL,"x"]};',
           f'sub {header} {raw["b"]}\' by {cursor(*model.reply(model.INITIAL,"o"),"o")};',
           f'sub {header} {group([n for c,n in raw.items() if c not in "hb"])}\' by {stop(model.INITIAL,"x","malformed")};']
    for (board,human),name in active.items():
        options=model.moves(board,human)
        bad=[raw[key] for key in '123456789' if key not in options]
        if bad:rules.append(f'sub {name} {group(bad)}\' by {stop(board,human,"invalid")};')
        for key,child in options.items():
            rules.append(f'sub {name} {raw[key]}\' by {cursor(*model.reply(child,human),human)};')
        rules.append(f'sub {name} {group([n for c,n in raw.items() if c not in "123456789"])}\' by {stop(board,human,"malformed")};')
    states=[header,*active.values(),*stopped.values()]
    finish=[f'sub {group(active.values())} end\' by status_ready;',f'sub {header} end\' by status_malformed;']
    by_status=defaultdict(list)
    for (board,human,status),name in stopped.items():by_status[status].append(name)
    finish += [f'sub {group(names)} end\' by status_{status};' for status,names in by_status.items()]
    pipeline=f.forward_program(['board',header,'r_last_none'],states,lasts,list(stopped.values()),rules,finish)
    return f.save(output,pipeline,[],[],1,compact=True,share_contours=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().with_name('tic-tac-toe-font.ttf'))
    build_font(parser.parse_args().output)


if __name__=='__main__':main()
