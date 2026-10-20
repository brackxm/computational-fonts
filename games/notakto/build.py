# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Build a complete three-board Notakto opponent in OpenType GSUB."""
import argparse
from collections import defaultdict
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'shared'))
from game_text import NAME_RECORDS, lettering, centered_lettering

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.otlLib.builder import buildCoverage, buildLookup
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib.tables import otTables

from model import CANONICAL, END, MAX_MOVES, START, dead, strategy_classes, winning

WIDTH, HEIGHT, UPM = 1800, 850, 1000
PASSES = (MAX_MOVES + 1) // 2 + 1  # Opening, paired turns, then end sentinel.
LEGAL_MASKS = tuple(tuple(m for m in range(512) if not dead(m) and not m >> cell & 1)
                    for cell in range(9))
STATUS = {'ready': 1, 'computer_won': 2, 'human_won': 3,
          'invalid': 4, 'malformed': 5, 'internal': 6}
LABELS = {'ready': 'Your turn', 'computer_won': 'Font wins', 'human_won': 'You win',
          'invalid': 'Invalid move', 'malformed': 'Check your input', 'internal': 'Game error'}
def rect(p, x, y, w, h):
    p.moveTo((x,y)); p.lineTo((x+w,y)); p.lineTo((x+w,y+h)); p.lineTo((x,y+h)); p.closePath()


def cell_xy(board, cell):
    row, col = divmod(cell,3)
    return 160+board*540+col*140, 550-row*140


def clock_wrapper(font, index, names):
    context = otTables.ContextSubst()
    context.Format = 3
    context.Coverage = [buildCoverage(names,font.getReverseGlyphMap())]
    context.GlyphCount = 1
    record = otTables.SubstLookupRecord()
    record.SequenceIndex, record.LookupListIndex = 0,index
    context.SubstLookupRecord, context.SubstCount = [record],1
    return buildLookup([context],table='GSUB',extension=True)


def build_font(output):
    classes, representatives = strategy_classes()
    glyphs, metrics, layers, order = {}, {}, {}, []
    def add(name, draw=None, advance=0, color=None, overlay=True):
        pen = TTGlyphPen(glyphs)
        if draw:
            draw(pen,-WIDTH if overlay else 0)
        glyphs[name] = pen.glyph()
        metrics[name] = (advance,0)
        order.append(name)
        if color is not None:
            layers[name] = [(name,color)]
        return name
    add('.notdef'); add('hidden'); add('begin'); add('end')
    raw = {chr(c):add(f'input_{c}') for c in range(32,128)}
    def frame(p, shift):
        centered_lettering(p,'Notakto',shift+900,750,18)
        for board in range(3):
            centered_lettering(p,chr(65+board),shift+310+board*540,650,12)
            for line in range(4):
                rect(p,shift+100+board*540+140*line,210,3,420)
                rect(p,shift+100+board*540,210+140*line,420,3)
            for cell in range(9):
                x,y=cell_xy(board,cell)
                lettering(p,str(cell+1),shift+x-45,y+50,5)
    add('board',frame,advance=WIDTH,color=0,overlay=False)
    board_names=[]
    for board in range(3):
        names=[]
        for mask in range(512):
            def marks(p, shift, board=board, mask=mask):
                for cell in range(9):
                    if mask>>cell&1:
                        x,y=cell_xy(board,cell)
                        for sign in (-1,1):
                            p.moveTo((shift+x-32,y+sign*(-32)-6))
                            p.lineTo((shift+x+32,y+sign*32-6))
                            p.lineTo((shift+x+32,y+sign*32+6))
                            p.lineTo((shift+x-32,y+sign*(-32)+6))
                            p.closePath()
                if dead(mask):
                    centered_lettering(p,'Closed',shift+310+board*540,150,9)
            names.append(add(f'r_board{board}_{mask}',marks,color=2 if dead(mask) else 1))
        board_names.append(names)
    class_names=[[add(f'r_class{board}_{i}') for i in range(len(representatives))] for board in range(3)]
    last_names=[add('r_last_none')]
    for board in range(3):
        for cell in range(9):
            def highlight(p,shift,board=board,cell=cell):
                x,y=cell_xy(board,cell)
                for args in ((x-49,y-49,98,4),(x-49,y+45,98,4),
                             (x-49,y-49,4,98),(x+45,y-49,4,98)):
                    a,b,w,h=args; rect(p,shift+a,b,w,h)
            last_names.append(add(f'r_last_{board}_{cell}',highlight,color=3))
    for status,code in STATUS.items():
        add('status_'+status,lambda p,s,status=status:centered_lettering(p,LABELS[status],s+900,60,11),
            advance=code,color=1 if code<4 else 2)
    for name in ('p_start','p_human','p_ai'):
        add(name)
    events={player:[add(f'{player}_{board}_{cell}') for board in range(3) for cell in range(9)]
            for player in ('human','ai')}
    marks=[n for n in order if n.startswith('r_')]
    definitions=['languagesystem DFLT dflt;','languagesystem latn dflt;',
                 '@marks = ['+' '.join(marks)+'];',
                 'table GDEF { GlyphClassDef , , @marks, ; } GDEF;']
    declarations=[]; stages=[]; coverages={}
    def group(names):return '['+' '.join(names)+']'
    def lookup(name,rules,coverage,expose=None,stage=True):
        flag='lookupflag 0;'
        if expose is not None:
            definitions.append(f'@filter_{name} = {group(expose)};')
            flag=f'lookupflag UseMarkFilteringSet @filter_{name};'
        declarations.append(f'lookup {name} useExtension {{\n{flag}\n'+'\n'.join(rules)+f'\n}} {name};')
        coverages[name]=coverage
        if stage:
            stages.append(name)

    lookup('SPACE',[f'sub {raw[" "]} by NULL;'],[raw[' ']],stage=False)
    initial=['board',*[b[0] for b in board_names],*[c[classes[0]] for c in class_names],
             'r_last_none','p_start']
    lookup('INIT',['sub begin by '+' '.join(initial)+';'],['begin'],stage=False)
    step=[f'sub p_start {raw["b"]} by p_ai;', 'sub p_human end by status_ready;']
    for board in range(3):
        for cell in range(9):
            step.append(f'sub p_human {raw[chr(65+board)]} {raw[str(cell+1)]} by human_{board}_{cell};')
    for state in ('p_start','p_human'):
        bad=[*raw.values(),'begin','.notdef','end']
        bad.remove(raw['b'] if state=='p_start' else 'end')
        step.append(f'sub {state} {group(bad)} by status_malformed;')
    lookup('STEP',step,['p_start','p_human'])

    for board in range(3):
        names=board_names[board]
        h_events=[f'human_{board}_{cell}' for cell in range(9)]
        checks=[]; updates=[]
        for cell in range(9):
            good=LEGAL_MASKS[cell]
            bad=[m for m in range(512) if m not in good]
            checks.append(f'sub {group([names[m] for m in bad])} human_{board}_{cell}\' by status_invalid;')
            updates.append(f'sub {group([names[m] for m in good])}\' human_{board}_{cell} by '
                           +group([names[m|1<<cell] for m in good])+';')
        lookup(f'CHECK_H{board}',checks,h_events,names+h_events)
        lookup(f'APPLY_H{board}',updates,names,names+h_events)

    dead_classes=[group([names[m] for m in range(512) if dead(m)]) for names in board_names]
    all_board=[name for names in board_names for name in names]
    lookup('H_TERMINAL',['sub '+' '.join(dead_classes)+f' {group(events["human"])}\' by status_computer_won;'],
           events['human'],all_board+events['human'])
    lookup('H_NEXT',[f'sub {group(events["human"])} by p_ai;'],events['human'])
    for board in range(3):
        refresh=[f'sub {group([board_names[board][m] for m in range(512) if classes[m]==i])} '
                 +group(class_names[board])+f'\' by {class_names[board][i]};'
                 for i in range(len(representatives))]
        lookup(f'CLASS{board}',refresh,class_names[board],board_names[board]+class_names[board])

    # Each context pair groups source masks by their FIRST winning cell, avoiding
    # a full-state glyph or a rule for every complete three-board position.
    actions={}
    for j,left in enumerate(representatives):
        for k,right in enumerate(representatives):
            by_move=defaultdict(list)
            for mask in range(512):
                if dead(mask):continue
                for cell in range(9):
                    if not mask>>cell&1 and not winning(tuple(sorted((CANONICAL[mask|1<<cell],left,right)))):
                        by_move[cell].append(mask); break
            actions[j,k]=by_move
    for board in range(3):
        others=[i for i in range(3) if i!=board]
        choices=[]
        for (j,k),by_move in actions.items():
            for cell,masks in by_move.items():
                choices.append('sub '+group([board_names[board][m] for m in masks])+' '
                    +class_names[others[0]][j]+' '+class_names[others[1]][k]
                    +f' p_ai\' by ai_{board}_{cell};')
        lookup(f'CHOOSE{board}',choices,['p_ai'],board_names[board]
               +class_names[others[0]]+class_names[others[1]]+['p_ai'])
    lookup('AI_MISSING',['sub p_ai by status_internal;'],['p_ai'])
    for board in range(3):
        updates=[]
        for cell in range(9):
            good=LEGAL_MASKS[cell]
            updates.append('sub '+group([board_names[board][m] for m in good])
                +f'\' ai_{board}_{cell} by '+group([board_names[board][m|1<<cell] for m in good])+';')
        ai_events=[f'ai_{board}_{cell}' for cell in range(9)]
        lookup(f'APPLY_AI{board}',updates,board_names[board],board_names[board]+ai_events)
    lookup('LAST',[f'sub {group(last_names)}\' ai_{board}_{cell} by r_last_{board}_{cell};'
                   for board in range(3) for cell in range(9)],last_names,last_names+events['ai'])
    lookup('AI_TERMINAL',['sub '+' '.join(dead_classes)+f' {group(events["ai"])}\' by status_human_won;'],
           events['ai'],all_board+events['ai'])
    lookup('AI_NEXT',[f'sub {group(events["ai"])} by p_human;'],events['ai'])
    # Finalization rejects residual parser states. A successful host query must
    # consume its explicit end sentinel, not merely exhaust the shaping clock.
    lookup('FINAL',[f'sub {group(["p_start","p_human","p_ai",*events["human"],*events["ai"]])} by status_malformed;'],
           ['p_start','p_human','p_ai',*events['human'],*events['ai']],stage=False)
    lookup('HIDE',['sub '+group([*raw.values(),'end','begin','.notdef'])+' by hidden;'],
           [*raw.values(),'end','begin','.notdef'],stage=False)
    fb=FontBuilder(UPM,isTTF=True)
    fb.setupGlyphOrder(order)
    cmap={ord(c):name for c,name in raw.items()}
    cmap.update({0xE100+ord(c):name for c,name in raw.items()})
    cmap.update({ord(START):'begin',ord(END):'end'})
    cmap.update({c:raw[' '] for c in (9,10,13)})
    fb.setupCharacterMap(cmap)
    for name,glyph in glyphs.items():
        glyph.recalcBounds(glyphs)
        metrics[name]=(metrics[name][0],getattr(glyph,'xMin',0))
    fb.setupGlyf(glyphs); fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=HEIGHT,descent=-30)
    fb.setupNameTable({'familyName':'Notakto Perfect Opponent','styleName':'Regular',
        'fullName':'Notakto Perfect Opponent Regular','psName':'NotaktoPerfectOpponent-Regular',
        'uniqueFontIdentifier':'NotaktoPerfectOpponent-1.0','version':'Version 1.0',
        'copyright':'Copyright 2026 Michael Brackx',
        'licenseDescription':'Licensed under the Apache License, Version 2.0',
        'licenseInfoURL':'https://www.apache.org/licenses/LICENSE-2.0', **NAME_RECORDS})
    fb.setupOS2(sTypoAscender=HEIGHT,sTypoDescender=-30,usWinAscent=HEIGHT,usWinDescent=30,fsType=0)
    fb.setupPost(); fb.setupMaxp(); fb.setupCOLR(layers,version=0)
    palette=('30484c','246b72','ae4a3c','bd872a')
    fb.setupCPAL([[tuple(int(c[i:i+2],16)/255 for i in (0,2,4))+(1.,) for c in palette]])
    font=fb.font
    feature='feature liga { lookup SPACE; lookup INIT; '+' '.join('lookup '+name+';' for name in stages)+' lookup FINAL; lookup HIDE; } liga;'
    addOpenTypeFeaturesFromString(font,'\n'.join(definitions+declarations+[feature]))
    liga=next(r.Feature for r in font['GSUB'].table.FeatureList.FeatureRecord if r.FeatureTag=='liga')
    space,init,*rest=liga.LookupListIndex
    effects,final,hide=rest[:-2],rest[-2],rest[-1]
    if len(effects)!=len(stages):
        raise RuntimeError(f'Unexpected lookup grouping: {len(effects)} != {len(stages)}')
    lookups=font['GSUB'].table.LookupList
    liga.LookupListIndex=[space,init]
    for _ in range(PASSES):
        for stage,index in zip(stages,effects):
            liga.LookupListIndex.append(len(lookups.Lookup))
            lookups.Lookup.append(clock_wrapper(font,index,coverages[stage]))
    for name,index in (('FINAL',final),('HIDE',hide)):
        liga.LookupListIndex.append(len(lookups.Lookup))
        lookups.Lookup.append(clock_wrapper(font,index,coverages[name]))
    liga.LookupCount=len(liga.LookupListIndex); lookups.LookupCount=len(lookups.Lookup)
    output=Path(output); output.parent.mkdir(parents=True,exist_ok=True)
    font.save(output)
    print(f'Saved {output}: {len(order)} glyphs, {lookups.LookupCount} lookups, {output.stat().st_size:,} bytes')
    font.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().with_name('notakto-font.ttf'))
    build_font(parser.parse_args().output)


if __name__=='__main__':main()
