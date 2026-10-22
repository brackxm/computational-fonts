# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Build playable Gardner chess: legal move generation entirely in GSUB."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys
import time
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'shared'))
from fontgame import GameFont, rect
from game_text import NAME_RECORDS, centered_lettering, lettering
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.otBase import USE_HARFBUZZ_REPACKER
from artwork import draw_piece
from opentype import Program, order_lookups
import model

PIECES = '.KQRBNPkqrbnp'
WORK, BOARD, CLOCK, RECORD = 2, 27, 52, 53
templates = model.templates


def attacks(target, by_white):
    """Attack tests in the *resulting* board, including pinned attackers."""
    tx, ty = target % 5, target // 5
    for kind, directions in (('N', model.KNIGHT), ('K', model.KING)):
        for dx, dy in directions:
            x, y = tx+dx, ty+dy
            if 0 <= x < 5 and 0 <= y < 5:
                yield {y*5+x: kind if by_white else kind.lower()}
    for dx in (-1, 1):
        x, y = tx+dx, ty+(-1 if by_white else 1)
        if 0 <= x < 5 and 0 <= y < 5:
            yield {y*5+x: 'P' if by_white else 'p'}
    for dx, dy in model.KING:
        path = {}
        x, y = tx+dx, ty+dy
        while 0 <= x < 5 and 0 <= y < 5:
            origin = y*5+x
            kinds = 'QR' if dx == 0 or dy == 0 else 'QB'
            yield {**path, origin: kinds if by_white else kinds.lower()}
            path[origin] = '.'
            x += dx
            y += dy


def build_font(output, *, book_path=None):
    started = time.monotonic()
    f = GameFont('Gardner Opponent', 1800, 1400, name_records=NAME_RECORDS)
    f.palette += ('e4eee9',)
    p = Program(f)
    raw = f.raw
    book_path = Path(book_path) if book_path else Path(__file__).with_name('book.json.gz')
    book=model.load_book(book_path)
    book_markers={move:f.add('r_book_'+move) for move in sorted(set(book.values()))}
    state_names = ('header', 'ready', 'ai', 'black_wait', 'black_try',
                   'probe', 'draw_before_ai', 'font_win', 'human_win', 'draw', 'invalid', 'malformed')
    states = {n: f.add('r_state_'+n) for n in state_names}
    phases = [(n,v) for n in (0,1) for v in ('q','r','b','n','p','.')]
    phase_states = {phase:f.add('r_ai_'+str(phase[0])+'_'+('empty' if phase[1]=='.' else phase[1])) for phase in phases}
    try_for = {(phase,i):f.add('r_try_'+str(n)+'_'+str(i)) for n,phase in enumerate(phases) for i in range(25)}
    tries = list(try_for.values())
    tries_by_target = {i:[try_for[phase,i] for phase in phases] for i in range(25)}
    human_tries=[f.add('r_human_try_'+str(i)) for i in range(25)]
    all_states = [*states.values(), *phase_states.values(), *tries, *human_tries, *book_markers.values()]
    last_none = f.add('r_last_none')
    all_moves = sorted({model.uci((o,t,promo)) for _,o,t,promo,_,_ in templates(True) if promo in ('','Q')} | set(book.values()))
    human_tokens = {model.square(o)+model.square(t)+promo:f.add('move_'+model.square(o)+model.square(t)+promo) for o in range(25) for t in range(25) for promo in ('','q','r','b','n')}
    all_states += list(human_tokens.values())
    last = {}
    def xy(i): return 450+(i%5)*180, 290+(i//5)*180
    for target in range(25):
        def highlight(pen, shift, target=target):
            x,y = xy(target)
            for dx,dy,w,h in ((6,6,168,4),(6,170,168,4),(6,6,4,168),(170,6,4,168)):
                rect(pen,shift+x+dx,y+dy,w,h)
            centered_lettering(pen,'FONT TO '+model.square(target).upper(),shift+900,130,9)
        last[target] = f.add('r_last_'+model.square(target), highlight, color=3)
    lasts = [last_none, *last.values()]
    cells = {bank: [{c: f.add(f'r_{bank}_{i}_{c if c != "." else "empty"}',
                 (lambda pen,shift,c=c,i=i: draw_piece(pen,shift+xy(i)[0]+90,xy(i)[1]+90,c)) if bank == 'cell' and c != '.' else None,
                 color=(0 if c.isupper() else 1) if bank == 'cell' and c != '.' else None)
                 for c in PIECES} for i in range(25)] for bank in ('work','cell')}
    A, B = cells['work'], cells['cell']
    eligible = [{c:f.add(f'r_eligible_{i}_{c if c != "." else "empty"}') for c in '.qrbnp'} for i in range(25)]
    counts = [f.add('r_count_'+str(i)) for i in range(151)]
    # Record: state, last move, 25 scratch cells, 25 displayed cells, quiet clock.
    def pattern(state, bank=None, constraints=None):
        result = [state, lasts, *[[*A[i].values(),*eligible[i].values()] for i in range(25)], *[list(c.values()) for c in B], counts]
        for i, chars in (constraints or {}).items():
            offset = WORK if bank == 'work' else BOARD
            result[offset+i] = [g for c in chars for g in ([A[i][c],eligible[i][c]] if bank=='work' and c in eligible[i] else [cells[bank][i][c]])]
        return result
    def rule(inputs, calls, back=()): return (inputs, calls, back)
    setters = {}
    def setter(target):
        if target not in setters:
            setters[target] = p.single('SET_'+target, {n: target for n in all_states})
        return setters[target]
    set_cell = {}
    for bank in cells:
        for c in PIECES:
            name = p.single('PUT_'+bank+'_'+('empty' if c=='.' else c),
                            {v:cells[bank][i][c] for i in range(25) for v in ([*A[i].values(),*eligible[i].values()] if bank=='work' else list(B[i].values()))})
            for i in range(25):set_cell[bank,i,c]=name
    copy = {}
    def copier(name, source, target, allowed):
        rules = []
        for c in PIECES:
            inputs = pattern(allowed, source, {name:c})
            rules.append(rule(inputs, [(WORK+name if target == 'work' else BOARD+name, set_cell[target,name,c])]))
        return p.context(f'COPY_{source}_{target}_{name}_'+str(len(copy)), rules)
    for source,target,allowed in (('work','cell',all_states),
                                  ('cell','work',[states['ai'],states['black_try']])):
        copy[source,target] = [copier(i,source,target,allowed) for i in range(25)]
    old_copy = []
    for i in range(25):
        rules=[]
        for c in PIECES:
            back=[B[i][c], *[list(B[j].values()) for j in range(i+1,25)], counts]
            rules.append(rule(pattern(all_states), [(WORK+i,set_cell['work',i,c])], back))
        old_copy.append(p.context('OLD_'+str(i), rules))
    put_count = {i:p.single('COUNT_SET_'+str(i), {n: counts[i] for n in counts}) for i in range(151)}
    copy_count = p.context('OLD_COUNT', [rule(pattern(all_states), [(CLOCK, put_count[i])], [counts[i]]) for i in range(151)])
    increment = p.single('INCREMENT', {counts[i]:counts[min(i+1,150)] for i in range(151)})
    tick = {}
    for kind, target in (('reset',put_count[0]), ('quiet',increment)):
        tick[kind] = p.context('TICK_'+kind, [rule(pattern([*human_tries,*tries]),[(CLOCK,target)])])
    reject_ai = p.single('REJECT_AI', {**{try_for[phase,i]:phase_states[phase] for phase in phases for i in range(25)}, states['draw']:states['human_win']})
    def check(name, bank, side, before, after, king=True, reject=None):
        rules=[]
        for target in range(25):
            for test in attacks(target,not side):
                if king: test={**test,target:'K' if side else 'k'}
                active = before if king else [try_for[phase,target] for phase in phases if phase[0]==0]
                rules.append(rule(pattern(active,bank,test),[(0,reject or setter(after))]))
        return p.context(name,rules)
    reject_black=p.single('REJECT_BLACK',{**{v:states['invalid'] for v in human_tries},states['draw']:states['font_win']})
    check_human = check('BLACK_KING','cell',False,[*human_tries,states['draw']],None,reject=reject_black)
    check_ai = check('WHITE_KING','cell',True,[*tries,states['draw']],None,reject=reject_ai)
    check_destination = check('WHITE_DESTINATION','cell',True,tries,None,False,reject=reject_ai)
    check_probe = check('BLACK_KING_WORK','work',False,states['black_try'],states['black_wait'])
    accept_human = p.single('ACCEPT_HUMAN',{v:states['ai'] for v in human_tries})
    accept_ai = p.single('ACCEPT_AI',{v:states['probe'] for v in tries})
    accept_probe = p.single('ACCEPT_PROBE',{states['black_try']:states['ready']})
    draw_before = p.context('QUIET_DRAW_BEFORE', [rule([*pattern(tries)[:CLOCK],counts[150]],[(0,setter(states['draw_before_ai']))])])
    target_marks={t:p.single('LAST_'+str(t),{v:last[t] for v in lasts}) for t in range(25)}
    mark={move:target_marks[model.parse_uci(move)[1]] for move in all_moves}
    human_ticks=[]
    for t in range(25):
        human_ticks.append(rule(pattern(human_tries[t],'work',{t:'.'}),[(CLOCK,increment)]))
        human_ticks.append(rule(pattern(human_tries[t],'work',{t:'QRBNP'}),[(CLOCK,put_count[0])]))
    human_tick=p.context('HUMAN_TICK',human_ticks)
    def geometry(template, victims):
        piece,o,t,promo,path,capture = template
        constraints={o:piece,t:victims,**{i:'.' for i in path}}
        return constraints
    # Ligatures consume their complete spelling (built by feaLib below).
    f.lookup('TOKENIZE', ['sub '+' '.join(raw[c] for c in move.upper()+';')+f' by {token};' for move,token in sorted(human_tokens.items(),key=lambda v:-len(v[0]))], [raw[c] for c in 'ABCDE'])
    human_rules=[]
    for temp in templates(False):
        piece,o,t,promo,path,capture=temp
        key=model.uci((o,t,promo))
        victims = 'KQRBNP' if capture else '.' if piece == 'p' else '.QRBNP'
        # Never allow capturing the opposing king.
        victims = victims.replace('K','')
        target_piece=(promo.lower() if promo else piece)
        calls=[(0,setter(human_tries[t])), (BOARD+o,set_cell['cell',o,'.']), (BOARD+t,set_cell['cell',t,target_piece]),
               (0,check_human),(0,tick['reset'] if piece=='p' else human_tick),(0,accept_human)]
        human_rules.append(rule(pattern(human_tokens[key],'work',geometry(temp,victims)),calls))
    human = p.context('HUMAN',human_rules)
    reject_human = p.single('REJECT_HUMAN',{v:states['invalid'] for v in human_tokens.values()})
    restore = p.context('RESTORE_INVALID',[rule(pattern(states['invalid']),[(0,n) for n in copy['work','cell']])])
    ai_ticks=[]
    for t in range(25):
        ai_ticks.append(rule(pattern(tries_by_target[t],'work',{t:'.'}),[(CLOCK,increment)]))
        ai_ticks.append(rule(pattern(tries_by_target[t],'work',{t:'qrbnp'}),[(CLOCK,put_count[0])]))
    tick_ai=p.context('TICK_AI',ai_ticks)
    # Exact opening rows use a small decision tree so a long book does not
    # require a linear scan of every opening on each turn.
    book_counter=0
    def book_tree(rows,depth=0,used=()):
        nonlocal book_counter
        ident=book_counter;book_counter+=1
        if len(rows)<=48 or depth==3:
            return p.exact('BOOK_LEAF_'+str(ident),[
                ([states['ai'],last_none,*[A[i][c] for i,c in enumerate(board)]],setter(book_markers[move]))
                for board,move in rows])
        choices=[]
        for i in range(25):
            if i in used:continue
            groups=defaultdict(list)
            for board,move in rows:groups[board[i]].append((board,move))
            if len(groups)>1:choices.append((max(map(len,groups.values())),i,groups))
        _,point,groups=min(choices,key=lambda v:(v[0],v[1]))
        return p.context('BOOK_NODE_'+str(ident),[
            rule(pattern(states['ai'],'work',{point:char}),[(0,book_tree(group,depth+1,(*used,point)))])
            for char,group in sorted(groups.items())])
    book_lookup=book_tree(sorted(book.items()))
    book_exec=[]
    for temp in templates(True):
        piece,o,t,promo,path,capture=temp
        key=model.uci((o,t,promo))
        if key not in book_markers:continue
        victims='qrbnp' if capture else '.' if piece=='P' else '.qrbnp'
        calls=[(0,setter(try_for[phases[0],t])),*[(0,n) for n in copy['work','cell']],
               (BOARD+o,set_cell['cell',o,'.']),(BOARD+t,set_cell['cell',t,promo or piece]),
               (1,mark[key]),(0,check_ai),(0,draw_before),
               (0,tick['reset'] if piece=='P' else tick_ai),(0,accept_ai)]
        book_exec.append(rule(pattern(book_markers[key],'work',geometry(temp,victims)),calls))
    book_run=p.context('BOOK_EXEC',book_exec)
    book_reject=p.single('BOOK_REJECT',{v:states['ai'] for v in book_markers.values()})
    # One White policy: safe captures, promotion, active quiet moves,
    # then legal sacrifices when no safe move exists. All choices test own king.
    white_templates = [t for t in templates(True) if not t[3] or t[3]=='Q']
    white_templates.sort(key=model.move_priority)
    prepare = {t:p.single('PREPARE_'+str(t),{phase_states[phase]:try_for[phase,t] for phase in phases}) for t in range(25)}
    unmark = p.single('UNMARK', {v:A[i][c] for i,entry in enumerate(eligible) for c,v in entry.items()})
    eligibility = {c:p.single('ELIGIBLE_'+('empty' if c=='.' else c), {A[i][c]:eligible[i][c] for i in range(25)}) for c in '.qrbnp'}
    ai_stages=[]
    for j,temp in enumerate(white_templates):
        piece,o,t,promo,path,capture=temp
        move=model.uci((o,t,promo))
        victims='qrbnp' if piece=='P' and capture else '.' if piece=='P' else '.qrbnp'
        inputs=pattern(list(phase_states.values()),'work',geometry(temp,victims))
        inputs[WORK+t]=[eligible[t][c] for c in victims]
        calls=[(0,prepare[t]),*[(0,n) for n in copy['work','cell']],
               (BOARD+o,set_cell['cell',o,'.']),(BOARD+t,set_cell['cell',t,promo or piece]),
               (1,mark[move]),(0,check_ai),(0,check_destination),(0,draw_before),
               (0,tick['reset'] if piece=='P' else tick_ai),(0,accept_ai)]
        ai_stages.append(p.context('AI_'+str(j),[rule(inputs,calls)]))
    ai=[]
    previous=states['ai']
    for number,phase in enumerate(phases):
        ai.append(p.single('PHASE_'+str(number),{previous:phase_states[phase]}))
        calls=[]
        for i in range(25):calls += [(WORK+i,unmark),(WORK+i,eligibility[phase[1]])]
        calls += [(0,n) for n in ai_stages]
        ai.append(p.context('SWEEP_'+str(number),[rule(pattern(phase_states[phase]),calls)]))
        previous=phase_states[phase]
    no_white = p.context('NO_WHITE',[rule(pattern([states['ai'],*phase_states.values()]),[(0,setter(states['draw']))])])
    # Restore the source board if White had no move, or a pre-move draw applies.
    reset_last=p.single('RESET_LAST',{v:last_none for v in lasts})
    terminal_restore = p.context('TERMINAL_RESTORE',[rule(
        pattern([states['human_win'],states['draw'],states['draw_before_ai']]),
        [(1,reset_last),*[(0,n) for n in copy['work','cell']]])])
    white_terminal=p.context('WHITE_TERMINAL',[rule(pattern(states['draw']),[(0,check_ai)])])
    begin_probe = p.single('BEGIN_PROBE',{states['probe']:states['black_wait']})
    black=[]
    for j,temp in enumerate(t for t in templates(False) if not t[3] or t[3]=='Q'):
        piece,o,t,promo,path,capture=temp
        victims='QRBNP' if capture else '.' if piece=='p' else '.QRBNP'
        calls=[(0,setter(states['black_try'])),*[(0,n) for n in copy['cell','work']],
               (WORK+o,set_cell['work',o,'.']),(WORK+t,set_cell['work',t,promo.lower() if promo else piece]),
               (0,check_probe),(0,accept_probe)]
        black.append(p.context('BLACK_'+str(j),[rule(pattern(states['black_wait'],'cell',geometry(temp,victims)),calls)]))
    no_black = p.context('NO_BLACK',[rule(pattern(states['black_wait']),[(0,setter(states['draw'])),(0,check_human)])])
    final_draw = p.context('QUIET_DRAW_AFTER',[rule([*pattern(states['ready'])[:CLOCK],counts[150]],[(0,setter(states['draw']))])])
    dead_tests=[]
    for point in (None,*range(25)):
        test={i:'Kk.' for i in range(25)}
        if point is not None:test[point]='BNbn'
        dead_tests.append(test)
    for color in (0,1):
        test={i:'Kk.Bb' if (i%5+i//5)%2==color else 'Kk.' for i in range(25)}
        dead_tests.append(test)
    dead = p.context('DEAD',[rule(pattern(states['ready'],'cell',test),[(0,setter(states['draw']))]) for test in dead_tests])
    dead_before = p.context('DEAD_BEFORE',[rule(pattern(states['ai'],'cell',test),[(0,setter(states['draw_before_ai']))]) for test in dead_tests])
    finish_draw = p.single('FINISH_PRE_DRAW',{states['draw_before_ai']:states['draw']})
    run_calls=[*[(0,n) for n in old_copy],(0,copy_count),*[(0,n) for n in copy['work','cell']],
               (0,human),(0,reject_human),(0,restore),*[(0,n) for n in copy['cell','work']],
               (0,dead_before),(0,book_lookup),(0,book_run),(0,book_reject),*[(0,n) for n in ai],(0,no_white),(0,terminal_restore),(0,white_terminal),(0,finish_draw),
               (0,begin_probe),*[(0,n) for n in black],(0,no_black),(0,final_draw),(0,dead)]
    def block(state):return [state,last_none,*[A[i]['.'] for i in range(25)],*[B[i]['.'] for i in range(25)],counts[0]]
    emit={token:block(token) for token in human_tokens.values()}
    emit[raw['b']]=block(states['ai'])
    emit_lookup=p.multiple('EMIT',emit)
    malformed=p.multiple('MALFORMED',{v:block(states['malformed']) for v in [*raw.values(),*human_tokens.values()]})
    freeze=p.multiple('FREEZE',{v:[] for v in [*raw.values(),*human_tokens.values()]})
    stopped=[states[n] for n in ('font_win','human_win','draw','invalid','malformed')]
    def old_context(allowed):return [allowed,lasts,*[[*A[i].values(),*eligible[i].values()] for i in range(25)],*[list(c.values()) for c in B],counts]
    trans_rules=[rule([[*raw.values(),*human_tokens.values()]],[(0,freeze)],old_context(stopped)),
                 rule([raw['b']],[(0,emit_lookup),*run_calls],old_context(states['header'])),
                 rule([list(human_tokens.values())],[(0,emit_lookup),*run_calls],old_context(states['ready'])),
                 rule([[*raw.values(),*human_tokens.values()]],[(0,malformed),*run_calls],old_context([states['header'],states['ready']]))]
    transition=p.context('TRANSITION',trans_rules)
    def frame(pen,shift):
        centered_lettering(pen,'GARDNER MINICHESS',shift+900,1280,12)
        centered_lettering(pen,'YOU BLACK   FONT WHITE',shift+900,185,7)
        for i in range(6):
            rect(pen,shift+450+i*180,290,3,900);rect(pen,shift+450,290+i*180,900,3)
        for i in range(5):
            lettering(pen,chr(65+i),shift+525+i*180,235,9);lettering(pen,str(i+1),shift+385,360+i*180,9)
    f.add('board',frame,advance=1800,overlay=False)
    labels={1:'YOUR TURN',2:'FONT WINS',3:'YOU WIN',4:'INVALID MOVE',5:'MALFORMED',7:'DRAW'}
    statuses={i:f.add('status_'+str(i),lambda pen,shift,label=label:centered_lettering(pen,label,shift+900,50,9),advance=i,color=2 if i in (4,5) else 1) for i,label in labels.items()}
    initial=['board',states['header'],last_none,*[A[i][c] for i,c in enumerate(model.INITIAL)],*[B[i][c] for i,c in enumerate(model.INITIAL)],counts[0]]
    init=p.multiple('INIT',{'begin':initial})
    status_lookups={code:p.single('STATUS_'+str(code),{'end':glyph}) for code,glyph in statuses.items()}
    finish=p.context('FINISH',[rule(['end'],[(0,status_lookups[code])],old_context(states[state])) for state,code in (('header',5),('ready',1),('font_win',2),('human_win',3),('draw',7),('invalid',4),('malformed',5))])
    space=p.multiple('SPACE',{raw[' ']:[]})
    # Hide complete older records in one pass. Per-cell history searches
    # would be quadratic and exhaust HarfBuzz's operation budget.
    data=[*all_states,*[v for c in A for v in c.values()],*[v for c in eligible for v in c.values()],*counts]
    hide=p.single('HIDE_RECORD',{v:'hidden' for v in [*data,*lasts,*[v for c in B for v in c.values()]]})
    prune=p.context('PRUNE',[(pattern(all_states),[(i,hide) for i in range(RECORD)],(),[all_states])])
    delete=p.multiple('DELETE',{v:[] for v in [*data,'hidden']})
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent,prefix='.build-') as temp:
        staging=Path(temp)/'stubs.ttf'
        completed=Path(temp)/'complete.ttf'
        f.save(staging,list(f.coverages),[],[],1)
        with TTFont(staging) as font:
            font.cfg[USE_HARFBUZZ_REPACKER]=True
            # Keep feaLib's tokenizer and install the direct register tables.
            feature=next(r.Feature for r in font['GSUB'].table.FeatureList.FeatureRecord if r.FeatureTag=='liga')
            existing=dict(zip(f.coverages,feature.LookupListIndex))
            print('Installing register tables',len(p.specs),flush=True)
            lookup_count=p.install(font,[])
            print('Saving register tables',flush=True)
            schedule=[existing['SPACE'],existing['TOKENIZE'],existing['INIT'],existing['TRANSITION'],existing['PRUNE'],existing['FINISH'],existing['DELETE']]
            feature.LookupListIndex=schedule;feature.LookupCount=len(schedule)
            order_lookups(font,schedule)
            font.save(completed)
        completed.replace(output)
    print(json.dumps({'glyphs':len(f.order),'lookups':lookup_count,'bytes':output.stat().st_size,'book_positions':len(book),'seconds':round(time.monotonic()-started,2)}),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path(__file__).with_name('gardner-font.ttf'))
    args=parser.parse_args()
    build_font(args.output)


if __name__=='__main__':main()
