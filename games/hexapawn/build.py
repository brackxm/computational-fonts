# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Build complete 3x3 Hexapawn with a perfect opponent on either side."""
import argparse
from collections import defaultdict
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'shared'))
from fontgame import GameFont,group,rect,circle,components
from game_text import NAME_RECORDS, lettering, centered_lettering
import model

WIDTH,HEIGHT,CELL=1800,1250,240
STATUS={'ready':1,'computer_won':2,'human_won':3,'invalid':4,'malformed':5,'internal':6}


def polygon(p,points):
    p.moveTo(points[0])
    for point in points[1:]:p.lineTo(point)
    p.closePath()


def cell_xy(index):return 540+(index%3)*CELL,300+(index//3)*CELL


def build_font(output):
    f=GameFont('Hexapawn Perfect Opponent',WIDTH,HEIGHT,name_records=NAME_RECORDS);f.palette+=('e4eee9',);raw=f.raw
    def frame(p,s):
        centered_lettering(p,'Hexapawn',s+900,1130,20)
        for i in range(4):
            rect(p,s+540+i*CELL,300,3,3*CELL);rect(p,s+540,300+i*CELL,3*CELL,3)
        for i in range(3):
            lettering(p,chr(65+i),s+645+i*CELL,245,10)
            lettering(p,str(i+1),s+465,395+i*CELL,10)
    def tint(p,s):
        for i in range(9):
            if (i//3+i%3)%2==0:
                x,y=cell_xy(i);rect(p,s+x,y,CELL,CELL)
    f.add('board',frame,advance=WIDTH,overlay=False)
    f.add('board_tint',tint,overlay=False);f.add('board_ink',frame,overlay=False)
    f.layers['board']=[('board_tint',4),('board_ink',0)]
    sprites={}
    for side in 'wb':
        for point in range(9):
            def pawn(p,s,side=side,point=point):
                x,y=cell_xy(point);x+=s+CELL//2;y+=CELL//2
                rect(p,x-41,y-50,82,16)
                polygon(p,[(x-29,y-34),(x+29,y-34),(x+15,y+6),(x-15,y+6)])
                circle(p,x,y+30,22)
                if side=='w':
                    polygon(p,[(x-34,y-45),(x-34,y-39),(x+34,y-39),(x+34,y-45)])
                    polygon(p,[(x-20,y-28),(x-10,y),(x+10,y),(x+20,y-28)])
                    circle(p,x,y+30,16,True)
            sprites[side,point]=f.add(f'pawn_{side}_{point}',pawn)
    boards=tuple(sorted({board for board,side in model.graph()}));ids={board:i for i,board in enumerate(boards)}
    paints={}
    for board in boards:
        pieces=[];layers=[]
        for side,color in (('w',0),('b',1)):
            names=[sprites[side,i] for i,c in enumerate(board) if c==side];pieces+=names
            name=f.add(f'paint_{side}_{ids[board]}',components(names));layers.append((name,color))
        name=f.add(f'position_{ids[board]}',components(pieces));paints[board]=name,layers
    for human,text in (('w','You: White    Font: Black'),('b','You: Black    Font: White')):
        f.add('role_'+human,lambda p,s,text=text:centered_lettering(p,text,s+900,175,8))
    for value,text in ((1,'You can force a win'),(-1,'Font can force a win')):
        f.add('hint_'+str(value).replace('-','m'),lambda p,s,text=text:centered_lettering(p,text,s+900,120,8))
    def state(name,board,human,hint=None):
        base,layers=paints[board];parts=[base,'role_'+human];layers=layers+[('role_'+human,0)]
        if hint is not None:
            hint_name='hint_'+str(hint).replace('-','m');parts.append(hint_name);layers.append((hint_name,0))
        result=f.add(name,components(parts));f.layers[result]=layers
        return result
    active={(board,human):state(f'r_active_{human}_{ids[board]}',board,human,model.solve(board,human)[0])
            for board,human in model.graph() if model.winner(board,human) is None}
    stopped={}
    def stop(board,human,status):
        key=board,human,status
        if key not in stopped:stopped[key]=state(f'r_{status}_{human}_{ids[board]}',board,human)
        return stopped[key]
    header=state('r_header',model.INITIAL,'w')
    lasts=[f.add('r_last_none')];last_names={}
    possible=sorted({key for board,side in model.graph() if model.winner(board,side) is None for key in model.moves(board,side)})
    for key in possible:
        target=(int(key[3])-1)*3+ord(key[2])-65
        def highlight(p,s,key=key,target=target):
            x,y=cell_xy(target)
            for dx,dy,w,h in ((6,6,CELL-12,5),(6,CELL-11,CELL-12,5),(6,6,5,CELL-12),(CELL-11,6,5,CELL-12)):
                rect(p,s+x+dx,y+dy,w,h)
            centered_lettering(p,'Font: '+key,s+900,65,9)
        name=f.add('r_last_'+key,highlight,color=3);lasts.append(name);last_names[key]=name
    labels=('Your turn','Font wins','You win','Invalid move','Check your input','Game error')
    for (status,code),label in zip(STATUS.items(),labels):
        f.add('status_'+status,lambda p,s,label=label:centered_lettering(p,label,s+900,10,10),advance=code,color=1 if code<4 else 2)
    squares=[model.square(i) for i in range(9)]
    tokens={a+b:f.add('move_'+a+b) for a in squares for b in squares}
    inputs=[*raw.values(),*tokens.values()]
    lex=[f'sub '+ ' '.join(raw[c] for c in key)+f' by {name};' for key,name in tokens.items()]
    def cursor(board,last,status,human):
        result=[active[board,human] if status=='ready' else stop(board,human,status)]
        if last is not None:result.append(last_names[last])
        return ' '.join(result)
    rules=[f'sub {header} {raw["h"]}\' by {active[model.INITIAL,"w"]};',
           f'sub {header} {raw["b"]}\' by {cursor(*model.reply(model.INITIAL,"b"),"b")};',
           f'sub {header} {group([n for n in inputs if n not in (raw["h"],raw["b"])])}\' by {stop(model.INITIAL,"w","malformed")};']
    for (board,human),name in active.items():
        options=model.moves(board,human)
        bad=[token for key,token in tokens.items() if key not in options]
        rules.append(f'sub {name} {group(bad)}\' by {stop(board,human,"invalid")};')
        for key,child in options.items():
            rules.append(f'sub {name} {tokens[key]}\' by {cursor(*model.reply(child,human),human)};')
        rules.append(f'sub {name} {group(raw.values())}\' by {stop(board,human,"malformed")};')
    states=[header,*active.values(),*stopped.values()]
    finish=[f'sub {group(active.values())} end\' by status_ready;',f'sub {header} end\' by status_malformed;']
    by_status=defaultdict(list)
    for (board,human,status),name in stopped.items():by_status[status].append(name)
    finish += [f'sub {group(names)} end\' by status_{status};' for status,names in by_status.items()]
    pipeline=f.forward_program(['board',header,'r_last_none'],states,lasts,list(stopped.values()),rules,finish,
        inputs=inputs,preprocess=[('MOVES',lex,[raw[c] for c in 'ABC'])])
    return f.save(output,pipeline,[],[],1)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().with_name('hexapawn-font.ttf'))
    build_font(parser.parse_args().output)


if __name__=='__main__':main()
