# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: GPL-3.0-only
"""Compile the pinned WeakC4 strategy and a human-history interpreter to GSUB.

Fixed tape: frame, 42 cells, mode, 42 annotations, 7 heights, 7 ranks,
count, decision, last column, parser. Tiny turn clocks call five shared drivers;
their lookup records address fixed slots and invoke shared helpers in order.
No complete boards or histories are enumerated.
"""
import argparse
import json
import math
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from gsub import Program, RegisterTape, glyph_class as cls
from strategy import BRANCHES, DIAGRAMS, OPENINGS, LINES, transition

HERE = Path(__file__).resolve().parent
WIDTH, HEIGHT, UPM = 1000, 1060, 1000
TURNS = 21
STATUS = {'ready': 1, 'win': 2, 'full': 3, 'malformed': 4,
          'trailing': 5, 'internal': 6, 'yellow': 7, 'draw': 8, 'limit': 9}
PALETTE = ('233f48', 'd54738', 'edbc40', 'e1e8df', 'fffaf0', '207d79')
# Original pixel lettering; independent of any base font.
PIXELS = dict(zip('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-', (
 '111101101101111','010110010010111','111001111100111','111001111001111',
 '101101111001001','111100111001111','111100111101111','111001010010010',
 '111101111101111','111101111001111','010101111101101','110101110101110',
 '111100100100111','110101101101110','111100110100111','111100110100100',
 '111100101101111','101101111101101','111010010010111','001001001101111',
 '101101110101101','100100100100111','101111111101101','101111111111101',
 '111101101101111','111101111100100','111101101111001','110101110101101',
 '111100111001111','111010010010010','101101101101111','101101101101010',
 '101101111111101','101101010101101','101101010010010','111001010100111',
 '000000111000000')))


def rect(p, x, y, w, h):
    p.moveTo((x, y)); p.lineTo((x+w, y)); p.lineTo((x+w, y+h)); p.lineTo((x, y+h)); p.closePath()


def circle(p, x, y, r, reverse=False):
    pts = [(round(x+r*math.cos(i*math.pi/16)), round(y+r*math.sin(i*math.pi/16))) for i in range(32)]
    if reverse: pts.reverse()
    p.moveTo(pts[0])
    for pt in pts[1:]: p.lineTo(pt)
    p.closePath()


def label(p, text, x, y, s=4):
    for c in text:
        for i, v in enumerate(PIXELS.get(c, '0'*15)):
            if v == '1': rect(p, x+i%3*s, y+(4-i//3)*s, s, s)
        x += 4*s


def mode_name(mode):
    return 'm_'+'_'.join(map(str, mode))


def build_font(output):
    glyphs, metrics, order, layers = {}, {}, [], {}
    def add(name, draw=None, advance=0, color=None):
        if name in glyphs: return name
        p = TTGlyphPen(None)
        if draw: draw(p)
        g = p.glyph(); g.recalcBounds(None)
        glyphs[name] = g; order.append(name)
        metrics[name] = (advance, getattr(g, 'xMin', 0))
        if color is not None: layers[name] = [(name, color)]
        return name
    def text(name, words, advance=0, color=0):
        return add(name, lambda p: label(p, words, -WIDTH+65, 55), advance, color)
    add('.notdef', lambda p: label(p, 'BAD INPUT', 30, 55), 17, 1)
    add('hidden')
    raw = {chr(i): add(f'raw{i}') for i in range(32, 128)}
    def frame(p):
        rect(p, 40, 220, 920, 660)
        for x in range(7):
            for y in range(6): circle(p, 110+130*x, 285+105*y, 43, True)
        for x in range(7): label(p, str(x+1), 103+130*x, 905, 5)
        label(p, 'RED - YELLOW', 65, 155, 4)
    add('board', frame, WIDTH, 0)
    cells = []
    for x in range(7):
        for y in range(6):
            names = [add(f'b_{x}_{y}_0')]
            for who in (1, 2):
                def checker(p, x=x, y=y, who=who):
                    cx, cy = -WIDTH+110+130*x, 285+105*y
                    circle(p, cx, cy, 39)
                    if who == 2: circle(p, cx, cy, 27, True)
                name = add(f'b_{x}_{y}_{who}', checker, color=who)
                # Color uses a filled disk; the base outline remains a ring
                # so Yellow stays distinct when COLR is unavailable.
                if who == 2: layers[name] = [(f'b_{x}_{y}_1', 2)]
                names.append(name)
            cells.append(names)
    modes = [('branch', i, m) for i in range(len(OPENINGS)) for m in (0, 1)]
    modes += [('leaf', i, m) for i in range(len(DIAGRAMS)) for m in (0, 1)]
    modes += [('urgent', 0, 0), ('invalid', 0, 0)]
    mode_g = [add(mode_name(m)) for m in modes]
    ann = [[add(f'a_{x}_{y}_{v}') for v in range(10)] for x in range(7) for y in range(6)]
    heights = [[add(f'h_{x}_{v}') for v in range(7)] for x in range(7)]
    ranks = [[add(f'r_{x}_{v}') for v in range(11)] for x in range(7)]
    counts = [add('cnt_none'), add('cnt_many')] + [add(f'cnt_{x}') for x in range(7)]
    decisions = [add('idle'), add('choose')] + [add(f'move{x+1}') for x in range(7)]
    last = []
    for x in range(7):
        def arrow(p, x=x):
            cx = -WIDTH+110+130*x
            p.moveTo((cx-17, 1000)); p.lineTo((cx+17, 1000)); p.lineTo((cx, 965)); p.closePath()
        last.append(add(f'last{x+1}', arrow, color=1))
    events = [add(f'event{x+1}') for x in range(7)]
    parsers = [add('p_'+s) for s in STATUS] + events
    for s, code in STATUS.items():
        words = {'ready':'YOUR TURN', 'win':'RED WINS', 'full':'COLUMN FULL', 'malformed':'BAD INPUT',
                 'trailing':'RED WINS - TRAILING INPUT', 'internal':'STRATEGY ERROR',
                 'yellow':'YELLOW WINS', 'draw':'DRAW', 'limit':'INPUT LIMIT'}[s]
        text('status_'+s, words, code, 5 if s == 'ready' else 1)
    # Fixed slots used by the single shared turn program.
    tape = RegisterTape(board=[['board']], cells=cells, mode=[mode_g], annotations=ann,
                        heights=heights, ranks=ranks, count=[counts], decision=[decisions],
                        last=[last], parser=[parsers])
    initial = ['board']+[c[1] if i == 18 else c[0] for i,c in enumerate(cells)]
    initial += [mode_name(('branch', OPENINGS.index(''), 0))]+[a[0] for a in ann]
    initial += [h[1] if x == 3 else h[0] for x,h in enumerate(heights)]
    initial += [r[10] for r in ranks]+['cnt_none', 'idle', 'last4', 'p_ready']
    marks = [name for name in order if name not in ('.notdef', 'board') and not name.startswith('status_')]
    program = Program(marks)
    lookup, calls = program.lookup, program.calls
    # INIT can only expand a b at the beginning, including literal ASCII input.
    expansion = lookup([f"sub {raw['b']} by {' '.join(initial)};"])
    bad_expansion = lookup([f"sub {cls([*raw.values(), '.notdef'])} by {' '.join(initial[:-1]+['p_malformed'])};"])
    init = lookup(['ignore sub '+cls(order)+f" {cls([*raw.values(), '.notdef'])}';",
                   f"sub {raw['b']}' lookup {expansion};",
                   f"sub {cls([*raw.values(), '.notdef'])}' lookup {bad_expansion};"])
    consume_rules = [f"sub p_ready {raw[str(x)]} by event{x};" for x in range(1, 8)]
    consume_rules += [f'sub p_ready {g} by p_malformed;' for c,g in raw.items() if c not in '1234567']
    consume_rules += ['sub p_ready .notdef by p_malformed;']
    consume_rules += [f'sub p_win {g} by p_trailing;' for g in [*raw.values(), '.notdef']]
    lookup(consume_rules, tape.at('parser'))
    # Reject a full human column before any cell, mode, or reply is changed.
    for x in range(7):
        lookup([f"sub {heights[x][6]} event{x+1}' by p_full;"], tape.at('parser'), heights[x]+events)
    program.stage('input', [*raw.values(), '.notdef'], ['p_ready', 'p_win'])
    def drop_checkers(player, selectors):
        for x in range(7):
            for y in range(6):
                cell = cells[x*6+y]
                lookup([f"sub {cell[0]}' {heights[x][y]} {selectors[x]} by {cell[player]};"],
                       tape.at('cells', x*6+y), cell+heights[x]+selectors)

    drop_checkers(2, events)
    program.stage('human drop', events)
    query_start = len(calls)
    derive = []
    for x in range(7):
        column = cells[x*6:x*6+6]
        rules = []
        for y in reversed(range(6)):
            context = [cls(column[y][1:])]+[cls(c) for c in column[y+1:]]
            rules.append('sub '+' '.join(context)+f" {cls(heights[x])}' by {heights[x][y+1]};")
        name = lookup(rules, tape.at('heights', x), [n for c in column for n in c]+heights[x])
        derive.append((tape.at('heights', x),name))
    lines = [sorted(line) for line in LINES]
    def detect(player):
        rules = []
        for line in lines:
            positions = {x*6+y for x,y in line}
            context = [cells[i][player] if i in positions else cls(cells[i])
                       for i in range(min(positions),42)]
            rules.append('sub '+' '.join(context)+f" {cls(events)}' by p_{'win' if player==1 else 'yellow'};")
        lookup(rules, tape.at('parser'), [n for c in cells for n in c]+events)
    detect(2)
    full = lookup(['sub '+' '.join(h[6] for h in heights)+f" {cls(events)}' by p_draw;"], tape.at('parser'),
                  [n for h in heights for n in h]+events)
    # Opening mode transitions only on a legal, nonterminal human event.
    rules = []
    for mode in modes:
        if mode[0] == 'branch':
            for yellow in range(1,8):
                rules.append(f"sub {mode_name(mode)}' event{yellow} by {mode_name(transition(mode,yellow))};")
    dispatch_call = len(calls)
    lookup(rules, tape.at('mode'), mode_g+events)
    # Reload fixed priority cells in place. Ten grouped rules per slot cover all
    # 768 oriented diagrams, with shared register glyphs and no board enumeration.
    for x in range(7):
        for y in range(6):
            a = ann[x*6+y]
            rules = []
            for v in range(10):
                group = [mode_name(m) for m in modes if m[0]=='leaf' and int(DIAGRAMS[m[1]][5-y][6-x if m[2] else x])==v]
                if group: rules.append(f"sub {cls(group)} {cls(a)}' by {a[v]};")
            lookup(rules, tape.at('annotations', x*6+y), mode_g+a)
    lookup([f"sub idle' {cls(events)} by choose;"], tape.at('decision'), decisions+events)
    # Tactics: win first, block second, leftmost column in each case.
    for who in (1,2):
        for x in range(7):
            patterns = [(y,[(a,b) for a,b in line if (a,b)!=(x,y)])
                        for y in range(6) for line in lines if (x,y) in line]
            positions = sorted({a*6+b for y,line in patterns for a,b in line})
            rules = []
            for y,line in patterns:
                required = {a*6+b for a,b in line}
                context = [cells[i][who] if i in required else cls(cells[i])
                           for i in positions if i >= min(required)]
                rules.append('sub '+' '.join(context)+f" {heights[x][y]} choose' by move{x+1};")
            lookup(rules, tape.at('decision'), [n for i in positions for n in cells[i]]+heights[x]+['choose'])
    rules = []
    for mode in modes:
        if mode[0] == 'branch':
            col = int(BRANCHES[OPENINGS[mode[1]]]); col = 8-col if mode[2] else col
            rules.append(f"sub {mode_name(mode)} choose' by move{col};")
    lookup(rules, tape.at('decision'), mode_g+['choose'])
    for x in range(7):
        lookup([f'sub {cls(ranks[x])} by {ranks[x][10]};'], tape.at('ranks', x))
        for y in range(6):
            a = ann[x*6+y]
            lookup([f"sub {a[v]} {heights[x][y]} {cls(ranks[x])}' by {ranks[x][v]};" for v in range(10)],
                   tape.at('ranks', x), a+heights[x]+ranks[x])
    for v in range(10):
        lookup([f'sub {cls(counts)} by cnt_none;'], tape.at('count'))
        for x in range(7):
            lookup([f"sub {ranks[x][v]} cnt_none' by cnt_{x};",
                    f"sub {ranks[x][v]} {cls(counts[2:])}' by cnt_many;"], tape.at('count'), ranks[x]+counts)
        lookup([f"sub cnt_{x} choose' by move{x+1};" for x in range(7)], tape.at('decision'), counts+['choose'])
    program.stage('strategy', events)
    drop_checkers(1, decisions[2:])
    program.stage('computer drop', decisions[2:])
    lookup([f"sub move{x+1} {cls(last)}' by last{x+1};" for x in range(7)], tape.at('last'), decisions+last)
    calls.extend(derive)
    detect(1)
    calls.append((tape.at('parser'), full))
    lookup([f"sub choose {cls(events)}' by p_internal;"], tape.at('parser'), decisions+events)
    lookup([f'sub {cls(events)} by p_ready;'], tape.at('parser'))
    lookup([f'sub {cls(decisions)} by idle;'], tape.at('decision'))
    program.stage('finish turn', events)
    # The last pass may just have won; inspect any remaining tail once more.
    tail = lookup([f"sub p_win {g} by p_trailing;" for g in [*raw.values(), '.notdef']]+
                  [f"sub p_ready {g} by p_limit;" for g in [*raw.values(), '.notdef']])
    final = lookup([f'sub p_{s} by status_{s};' for s in STATUS])
    hide = lookup([f"sub {cls([*raw.values(), '.notdef'])} by NULL;"])
    fb = FontBuilder(UPM, isTTF=True); fb.setupGlyphOrder(order)
    cmap = {ord(c):g for c,g in raw.items()}
    cmap.update({0xe100+ord(c):g for c,g in raw.items()})
    fb.setupCharacterMap(cmap); fb.setupGlyf(glyphs); fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=HEIGHT, descent=-20)
    fb.setupNameTable({'familyName':'Connect Four Perfect', 'styleName':'Regular',
        'uniqueFontIdentifier':'ConnectFourPerfect-1.0','fullName':'Connect Four Perfect Regular',
        'psName':'ConnectFourPerfect-Regular','version':'Version 1.0',
        16:'Connect Four Perfect',17:'Regular',
        'copyright':'Copyright 2026 Michael Brackx. Strategy by 2swap and WeakC4 contributors.',
        'licenseDescription':'GPL-3.0-only. Derived from WeakC4 revision 51dc8383472c63aa6e6796a9ef306662eb8bd4bf. See upstream/LICENSE and PROVENANCE.md.',
        'licenseInfoURL':'https://www.gnu.org/licenses/gpl-3.0.html'})
    fb.setupOS2(sTypoAscender=HEIGHT,sTypoDescender=-20,usWinAscent=HEIGHT,usWinDescent=20,fsType=0)
    fb.setupPost(); fb.setupMaxp(); fb.setupCOLR(layers,version=0)
    fb.setupCPAL([[tuple(int(c[i:i+2],16)/255 for i in (0,2,4))+(1.0,) for c in PALETTE]])
    font = fb.font
    indices, records = program.attach(font, tape, init,
        [(parsers, tail), (parsers, final), ([*raw.values(), '.notdef'], hide)], TURNS)
    lookups = font['GSUB'].table.LookupList.Lookup
    font['head'].created = font['head'].modified = 3800000000
    output = Path(output); output.parent.mkdir(parents=True,exist_ok=True)
    font.save(output)
    font.flavor='woff2'; font.save(output.with_suffix('.woff2'))
    stats = {'glyphs':len(order),'lookups':len(lookups),'driver_records':len(calls),'shared_stages':len(program.stages),'turns':TURNS,
             'ttf_bytes':output.stat().st_size,'woff2_bytes':output.with_suffix('.woff2').stat().st_size}
    output.with_suffix('.json').write_text(json.dumps(stats,indent=2)+'\n')
    abi = {'slots':tape.slots, 'records':records, 'query_start':query_start, 'dispatch_call':dispatch_call,
           'final':indices[final], 'hide':indices[hide], 'offsets':tape.offsets,
           'stages':[{'name':name, 'start':first, 'end':last} for name,first,last,guard,anchor in program.stages]}
    output.with_suffix('.abi.json').write_text(json.dumps(abi,separators=(',',':'))+'\n')
    print(json.dumps(stats))
    return stats


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE/'connect-four-font.ttf')
    build_font(parser.parse_args().output)
