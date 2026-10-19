# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Build a complete forward-reading Mū tōrere opponent in OpenType GSUB."""
import argparse
from collections import defaultdict
from math import cos,sin,pi,hypot
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'shared'))
from fontgame import GameFont,group,lettering
import model

WIDTH,HEIGHT=1800,1300
STATUS={'ready':1,'computer_won':2,'human_won':3,'invalid':4,'malformed':5,'internal':6,'draw':7}
POINTS=tuple((round(900+380*sin(i*pi/4)),round(700+380*cos(i*pi/4))) for i in range(8))+((900,700),)


def caption(p,text,shift,y,size=10):
    lettering(p,text,shift+900-2*size*len(text),y,size)


def circle(p,x,y,r,reverse=False):
    sign=-1 if reverse else 1
    p.moveTo((x+r,y))
    for control,end in (((x+r,y+sign*r),(x,y+sign*r)),((x-r,y+sign*r),(x-r,y)),
                        ((x-r,y-sign*r),(x,y-sign*r)),((x+r,y-sign*r),(x+r,y))):
        p.qCurveTo(control,end)
    p.closePath()


def build_font(output):
    f=GameFont('Mu Torere Perfect Opponent',WIDTH,HEIGHT);raw=f.raw
    def frame(p,s):
        caption(p,'MU TORERE',s,1210,13)
        edges=[(i,(i+1)%8) for i in range(8)]+[(i,8) for i in range(8)]
        for a,b in edges:
            ax,ay=POINTS[a];bx,by=POINTS[b]
            dx,dy=bx-ax,by-ay;length=hypot(dx,dy);dx/=length;dy/=length
            ax+=55*dx;ay+=55*dy;bx-=55*dx;by-=55*dy
            p.moveTo((s+ax-2*dy,ay+2*dx));p.lineTo((s+bx-2*dy,by+2*dx))
            p.lineTo((s+bx+2*dy,by-2*dx));p.lineTo((s+ax+2*dy,ay-2*dx));p.closePath()
        for i,(x,y) in enumerate(POINTS):
            circle(p,s+x,y,55);circle(p,s+x,y,52,True)
            if i<8:
                lx,ly=900+475*sin(i*pi/4),700+475*cos(i*pi/4)
            else:lx,ly=985,740
            lettering(p,str(i+1),s+round(lx)-11,round(ly)-17,7)
    f.add('board',frame,advance=WIDTH,color=0,overlay=False)
    sprites={}
    for player in 'ha':
        for point,(x,y) in enumerate(POINTS):
            def draw(p,s,x=x,y=y,player=player):
                circle(p,s+x,y,47)
                if player=='a':circle(p,s+x,y,32,True)
            sprites[player,point]=f.add(f'disc_{player}_{point}',draw)
    def composite(names):
        def draw(p,s):
            for name in names:p.addComponent(name,(1,0,0,1,0,0))
        return draw
    paints={}
    for position in model.POSITIONS:
        index=model.IDS[position];layers=[];all_sprites=[]
        for player,color in (('h',2),('a',1)):
            pieces=[sprites[player,i] for i,c in enumerate(position) if c==player]
            all_sprites+=pieces
            name=f'paint_{player}_{index}';f.add(name,composite(pieces));layers.append((name,color))
        base=f'position_{index}';f.add(base,composite(all_sprites))
        paints[position]=(base,layers)
    hints={0:'PERFECT PLAY DRAWS',-1:'FONT CAN FORCE A WIN',1:'YOU CAN FORCE A WIN'}
    for value,text in hints.items():
        f.add('hint_'+str(value).replace('-','m'),lambda p,s,text=text:caption(p,text,s,145,9))
    active={}
    values,_=model.solve()
    for position in model.POSITIONS:
        if not model.moves(position,'h'):continue
        base,layers=paints[position];hint='hint_'+str(values[position,'h']).replace('-','m')
        name=f.add(f'r_active_{model.IDS[position]}',composite([base,hint]))
        f.layers[name]=layers+[(hint,0)];active[position]=name
    stopped={}
    def stop(position,status):
        key=position,status
        if key not in stopped:
            base,layers=paints[position]
            name=f.add(f'r_{status}_{model.IDS[position]}',composite([base]))
            f.layers[name]=layers;stopped[key]=name
        return stopped[key]
    base,layers=paints[model.INITIAL]
    header=f.add('r_header',composite([base]));f.layers[header]=layers
    lasts=[f.add('r_last_none')];last_names={}
    edges=[(a,b) for a in range(9) for b in range(9)
           if a!=b and (a==8 or b==8 or (a-b)%8 in (1,7))]
    for source,target in edges:
        def mark(p,s,source=source,target=target):
            x,y=POINTS[target];circle(p,s+x,y,64);circle(p,s+x,y,60,True)
            caption(p,f'FONT {source+1} TO {target+1}',s,80,10)
        name=f.add(f'r_last_{source}_{target}',mark,color=3)
        lasts.append(name);last_names[source,target]=name
    labels=('YOUR TURN','FONT WINS','YOU WIN','INVALID MOVE','MALFORMED','INTERNAL ERROR','DRAW AGREED')
    for (status,code),label in zip(STATUS.items(),labels):
        f.add('status_'+status,lambda p,s,label=label:caption(p,label,s,15,10),advance=code,color=1 if code in (1,2,3,7) else 2)

    def cursor_result(position,last,status):
        result=[active[position] if status=='ready' else stop(position,status)]
        if last is not None:result.append(last_names[last])
        return ' '.join(result)
    rules=[f'sub {header} {raw["h"]}\' by {active[model.INITIAL]};']
    rules.append(f'sub {header} {raw["b"]}\' by {cursor_result(*model.reply(model.INITIAL))};')
    rules += [f'sub {header} {raw[mode]}\' by {active[model.starts()[mode]]};' for mode in 'wl']
    rules.append(f'sub {header} {group([name for c,name in raw.items() if c not in model.starts()])}\' by {stop(model.INITIAL,"malformed")};')
    for position,name in active.items():
        options=model.moves(position,'h')
        bad=[raw[str(source+1)] for source in range(9) if source not in options]
        if bad:rules.append(f'sub {name} {group(bad)}\' by {stop(position,"invalid")};')
        for source,child in options.items():
            rules.append(f'sub {name} {raw[str(source+1)]}\' by {cursor_result(*model.reply(child))};')
        draw_status='draw' if values[position,'h']>=0 else 'invalid'
        rules.append(f'sub {name} {raw["="]}\' by {stop(position,draw_status)};')
        malformed=[n for c,n in raw.items() if c not in '123456789=']
        rules.append(f'sub {name} {group(malformed)}\' by {stop(position,"malformed")};')
    all_states=[header,*active.values(),*stopped.values()]
    finish=[f'sub {group(active.values())} end\' by status_ready;',f'sub {header} end\' by status_malformed;']
    by_status=defaultdict(list)
    for (position,status),name in stopped.items():by_status[status].append(name)
    finish += [f'sub {group(names)} end\' by status_{status};' for status,names in by_status.items()]
    names=f.forward_program(['board',header,'r_last_none'],all_states,lasts,list(stopped.values()),rules,finish)
    return f.save(output,names,[],[],1)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().with_name('mu-torere-font.ttf'))
    build_font(parser.parse_args().output)


if __name__=='__main__':main()
