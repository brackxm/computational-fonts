# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Original fixed-register GSUB interpreter for the verified independent policy.

Policy IDs use two registers, so the number of policies is not limited by the
OpenType glyph count. Hierarchical dispatch selects by both registers instead
of scanning the entire opening graph. No GPL modules or strategy inputs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import independent as c

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'shared'))
from fontgame import GameFont, circle, group, rect
from game_text import NAME_RECORDS, centered_lettering
from fontTools.otlLib.builder import buildCoverage, buildLookup
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables as ot

RADIX = 256
POLICY_RADIX = 256
LOW_COUNT = 256
STATUS = {'ready': 1, 'win': 2, 'full': 3, 'malformed': 4, 'trailing': 5,
          'internal': 6, 'yellow': 7, 'draw': 8, 'limit': 9}


def build(controller, output, initial_history='4'):
    if not controller.get('complete'):
        raise ValueError('cannot compile an incomplete policy')
    first = controller['initial_action']
    if first[0] != 'move':
        raise ValueError('kernel requires a prescribed first Red move')
    if len(initial_history) != 1 or int(initial_history) != first[1]:
        raise ValueError('first move does not match initial board')
    modes, policies = controller['modes'], controller['policies']
    branches = [i for i, mode in enumerate(modes) if mode[0] == 'branch']
    branch_index = {mode: i for i, mode in enumerate(branches)}
    branch_blocks = (len(branches)+RADIX-1)//RADIX
    policy_blocks = (len(policies)+POLICY_RADIX-1)//POLICY_RADIX
    f = GameFont('Connect Four Independent', 1000, 1060, name_records=NAME_RECORDS)
    f.palette = ('233f48', 'd54738', 'edbc40', 'e1e8df', 'fffaf0', '207d79')

    def frame(pen, shift):
        rect(pen, 40, 220, 920, 660)
        for col in range(7):
            for row in range(6):
                circle(pen, 110+130*col, 285+105*row, 43, reverse=True)
        for col in range(7):
            centered_lettering(pen, str(col+1), 110+130*col, 905, 8)
        centered_lettering(pen, 'Red vs Yellow', 500, 155, 7, weight='regular')

    f.add('board', frame, advance=1000, color=0, overlay=False)
    cells = []
    for col in range(7):
        for row in range(6):
            names = [f.add(f'r_c{col}_{row}_0')]
            for player in (1, 2):
                def disc(pen, shift, col=col, row=row, player=player):
                    circle(pen, shift+110+130*col, 285+105*row, 39)
                    if player == 2:
                        circle(pen, shift+110+130*col, 285+105*row, 27, reverse=True)
                names.append(f.add(f'r_c{col}_{row}_{player}', disc, color=player))
            f.layers[names[2]] = [(names[1], 2)]
            cells.append(names)
    heights = [[f.add(f'r_h{col}_{row}') for row in range(7)] for col in range(7)]
    hi_keys = [('b', i) for i in range(branch_blocks)]+[('p', i) for i in range(policy_blocks)]+[('t', 0)]
    high = {key: f.add(f'r_hi_{key[0]}_{key[1]}') for key in hi_keys}
    low = [f.add(f'r_lo_{i}') for i in range(LOW_COUNT)]
    choices = [[f.add(f'r_choice_{human}_{lo}') for lo in range(LOW_COUNT)] for human in range(7)]
    scratch_hi = f.add('r_next_hi_unknown')
    scratch_lo = f.add('r_next_lo_unknown')
    actions = ['choose', 'error', *map(str, range(1, 8))]
    new_hi = {(key, action): f.add(f'r_next_hi_{key[0]}_{key[1]}_{action}')
              for key in hi_keys for action in actions}
    new_lo = [f.add(f'r_next_lo_{i}') for i in range(LOW_COUNT)]
    # Profile numbers are local to each column, so seven dictionaries share
    # the same glyph alphabet. Decoding is explicitly targeted by column.
    profile_vectors = [sorted({tuple(p[6*col:6*col+6]) for p in policies}) for col in range(7)]
    profile_ids = [{v: i for i, v in enumerate(values)} for values in profile_vectors]
    profiles = [f.add(f'r_profile_{i}') for i in range(max(map(len, profile_vectors)))]
    copied_low = [f.add(f'r_copy_lo_{i}') for i in range(LOW_COUNT)]
    ranks = [[f.add(f'r_rank_{col}_{level}') for level in range(43)] for col in range(7)]
    decisions = {name: f.add('r_d_'+name) for name in ['idle', 'choose', 'error', *map(str, range(1, 8))]}
    last = []
    for col in range(7):
        def arrow(pen, shift, col=col):
            x = shift+110+130*col
            pen.moveTo((x-17, 1000)); pen.lineTo((x+17, 1000)); pen.lineTo((x, 965)); pen.closePath()
        last.append(f.add(f'r_last_{col+1}', arrow, color=1))
    parser = {name: f.add('r_p_'+name) for name in [*STATUS, 'active', *[f'h{i}' for i in range(1, 8)]]}
    humans = [parser[f'h{i}'] for i in range(1, 8)]
    for name, code in STATUS.items():
        label = {'ready': 'Your turn', 'win': 'Red wins', 'full': 'Column full', 'malformed': 'Bad input',
                 'trailing': 'Red wins - trailing input', 'internal': 'Strategy error', 'yellow': 'Yellow wins',
                 'draw': 'Draw', 'limit': 'Input limit'}[name]
        f.add('status_'+name, lambda pen, shift, label=label:
              centered_lettering(pen, label, shift+500, 55, 8), advance=code, color=5 if name == 'ready' else 1)
    f.add('r_placeholder_in'); f.add('r_placeholder_out')

    def encoding(mode):
        tag, *args = modes[mode]
        if tag == 'branch':
            index = branch_index[mode]
            return ('b', index//RADIX), index%RADIX
        if tag == 'policy':
            index = args[0]
            return ('p', index//POLICY_RADIX), index%POLICY_RADIX
        return ('t', 0), 0

    start_hi, start_lo = encoding(first[2])
    red, yellow, _ = c.parse(initial_history)
    initial = ['board']+[names[1] if red & (1 << (7*(i//6)+i%6)) else names[0]
                         for i, names in enumerate(cells)]
    initial += [height[1 if col == first[1]-1 else 0] for col, height in enumerate(heights)]
    initial += [high[start_hi], low[start_lo], scratch_hi, scratch_lo]
    initial += [row[42] for row in ranks]+[decisions['idle'], last[first[1]-1], parser['ready']]

    slots = [*cells, *heights, list(high.values()), low, [scratch_hi, *new_hi.values()], [scratch_lo, *new_lo],
             *ranks, list(decisions.values()), last, list(parser.values())]
    assert len(slots) == 63
    names = [f'@slot{i}' for i in range(len(slots))]
    f.definitions.extend(f'{name} = {group(values)};' for name, values in zip(names, slots))
    H, D, LAST, P = 42, 60, 61, 62

    def pattern(start, stop, overrides=None, marked=None):
        overrides = overrides or {}
        return ' '.join(overrides.get(i, names[i])+ ("'" if i == marked else '') for i in range(start, stop))

    def lookup(name, rules, coverage, expose=None):
        f.lookup(name, rules, coverage, expose)

    raw = [*f.raw.values(), '.notdef']
    bad_initial = initial[:-1]+[parser['malformed']]
    lookup('INIT', [f'ignore sub {group(f.order)} {group(raw)}\';',
                    f'sub {f.raw["b"]}\' by '+ ' '.join(initial)+';',
                    f'sub {group(raw)}\' by '+ ' '.join(bad_initial)+';'], raw)
    consume = [f'sub {parser["ready"]} {f.raw[str(i)]} by {parser[f"h{i}"]};' for i in range(1, 8)]
    consume += [f'sub {parser["ready"]} {group([v for ch,v in f.raw.items() if ch not in "1234567"]+[".notdef"])} by {parser["malformed"]};',
                f'sub {parser["win"]} {group(raw)} by {parser["trailing"]};']
    lookup('CONSUME', consume, [parser['ready'], parser['win']])
    reject = [f'sub {pattern(H+col, P+1, {H+col: heights[col][6], P: parser[f"h{col+1}"]}, P)} by {parser["full"]};'
              for col in range(7)]
    lookup('FULL', reject, humans)

    def drops(player):
        rules = []
        for col in range(7):
            for row in range(6):
                i = 6*col+row
                override = {i: cells[i][0], H+col: heights[col][row],
                            P: parser[f'h{col+1}'] if player == 2 else parser['active']}
                if player == 1:
                    override[D] = decisions[str(col+1)]
                rules.append(f'sub {pattern(i, P+1, override, i)} by {cells[i][player]};')
        return rules

    lookup('HUMAN_DROP', drops(2), [cell[0] for cell in cells])

    def height_updates(human):
        rules = []
        for col in range(7):
            for row in range(6):
                override = {H+col: heights[col][row], P: parser[f'h{col+1}'] if human else parser['active']}
                if not human:
                    override[D] = decisions[str(col+1)]
                rules.append(f'sub {pattern(H+col, P+1, override, H+col)} by {heights[col][row+1]};')
        return rules

    lookup('HUMAN_HEIGHT', height_updates(True), [v for row in heights for v in row[:-1]])

    def detect(player, phase):
        rules = []
        for line in c.ARRAY_LINES:
            indices = [6*col+row for row, col in line]
            override = {i: cells[i][player] for i in indices}
            override[P] = phase
            rules.append(f'sub {pattern(min(indices), P+1, override, P)} by {parser["win" if player == 1 else "yellow"]};')
        return rules

    def draw(phase):
        override = {H+col: heights[col][6] for col in range(7)}
        override[P] = phase
        return f'sub {pattern(H, P+1, override, P)} by {parser["draw"]};'

    lookup('HUMAN_END', [*detect(2, group(humans)), draw(group(humans))], humans)
    lookup('DROP_SCRATCH', [f'sub {group([scratch_hi, scratch_lo])}\' {group([scratch_hi, scratch_lo])} {group(humans)} by NULL;',
                            f'sub {group([scratch_hi, scratch_lo])}\' {group(humans)} by NULL;'],
           [scratch_hi, scratch_lo], [scratch_hi, scratch_lo, *humans])
    lookup('DISPATCH', ['sub r_placeholder_in by r_placeholder_out;'], list(high.values()))
    lookup('OLD_HIGH', [f'sub {group(high.values())}\' {group(humans)} by NULL;'], list(high.values()),
           [*high.values(), *humans])
    lookup('DECISION', [f'sub {group([glyph for (key, action), glyph in new_hi.items() if action == name])} {decisions["idle"]}\' {group(humans)} by {decisions[name]};'
                        for name in actions], [decisions['idle']], [*new_hi.values(), decisions['idle'], *humans])
    lookup('NEW_HIGH', [f'sub {glyph} by {high[key]};' for (key, action), glyph in new_hi.items()], list(new_hi.values()))
    lookup('NEW_LOW', [f'sub {new_lo[i]} by {low[i]} {scratch_hi} {scratch_lo};' for i in range(LOW_COUNT)], new_lo)

    lookup('ACTIVATE', [f'sub {group(humans)} by {parser["active"]};'], humans)

    def tactical(player):
        rules = []
        for col in c.ORDER:
            for row in range(6):
                target = 6*col+row
                for line in c.ARRAY_LINES:
                    indices = [6*x+y for y, x in line]
                    if target not in indices:
                        continue
                    override = {i: cells[i][player] for i in indices if i != target}
                    override.update({target: cells[target][0], H+col: heights[col][row],
                                     D: decisions['choose'], P: parser['active']})
                    rules.append(f'sub {pattern(min(indices), P+1, override, D)} by {decisions[str(col+1)]};')
        return rules

    lookup('WIN', tactical(1), [decisions['choose']])
    lookup('BLOCK', tactical(2), [decisions['choose']])
    lookup('RESET_RANKS', [f'sub {group(row[:-1])} by {row[42]};' for row in ranks],
           [v for row in ranks for v in row[:-1]])
    lookup('COPY_LOW', [f'sub {low[i]} {ranks[0][42]}\' {decisions["choose"]} {parser["active"]} by {copied_low[i]};'
                        for i in range(LOW_COUNT)], low,
           [*low, ranks[0][42], decisions['choose'], parser['active']])
    # Shrink before expanding the seven profiles, keeping the driver within
    # its 64-glyph match. Both operations run only for active policy choices.
    rank_tail = [row[42] for row in ranks[1:]]
    drop_tail = [f'sub {ranks[col][42]}\' '+ ' '.join(row[42] for row in ranks[col+1:])+
                 f' {decisions["choose"]} {parser["active"]} by NULL;' for col in range(1, 7)]
    lookup('DROP_RANK_TAIL', drop_tail,
           rank_tail, [*rank_tail, decisions['choose'], parser['active']])
    lookup('EXPAND_PROFILES', ['sub r_placeholder_in by r_placeholder_out;'],
           [high['p', i] for i in range(policy_blocks)])
    for col in range(7):
        lookup(f'READ_PROFILE_{col}', ['sub r_placeholder_in by r_placeholder_out;'], profiles)
    select = []
    for level in range(42):
        for col in c.ORDER:
            select.append(f'sub {pattern(53+col, P+1, {53+col: ranks[col][level], D: decisions["choose"], P: parser["active"]}, D)} by {decisions[str(col+1)]};')
    lookup('SELECT', select, [decisions['choose']])
    lookup('RED_DROP', drops(1), [cell[0] for cell in cells])
    lookup('RED_HEIGHT', height_updates(False), [v for row in heights for v in row[:-1]])
    lookup('LAST', [f'sub {decisions[str(col+1)]} {group(last)}\' {parser["active"]} by {last[col]};' for col in range(7)], last)
    lookup('RED_END', [*detect(1, parser['active']), draw(parser['active'])], [parser['active']])
    lookup('ERROR', [f'sub {group([decisions["choose"], decisions["error"]])} {group(last)} {parser["active"]}\' by {parser["internal"]};'], [parser['active']])
    lookup('READY', [f'sub {parser["active"]} by {parser["ready"]};'], [parser['active']])
    lookup('IDLE', [f'sub {group([v for k,v in decisions.items() if k != "idle"])} by {decisions["idle"]};'], list(decisions.values()))
    lookup('TAIL', [f'sub {parser["win"]} {group(raw)} by {parser["trailing"]};',
                    f'sub {parser["ready"]} {group(raw)} by {parser["limit"]};'], [parser['win'], parser['ready']])
    lookup('FINAL', [f'sub {parser[name]} by status_{name};' for name in STATUS], list(parser.values()))
    lookup('HIDE', [f'sub {group(raw)} by NULL;'], raw)
    stages = ['CONSUME', 'FULL', 'HUMAN_DROP', 'HUMAN_HEIGHT', 'HUMAN_END', 'DROP_SCRATCH', 'DISPATCH',
              'OLD_HIGH', 'DECISION', 'NEW_HIGH', 'NEW_LOW', 'ACTIVATE', 'WIN', 'BLOCK', 'RESET_RANKS',
              'COPY_LOW', 'DROP_RANK_TAIL', 'EXPAND_PROFILES', *[f'READ_PROFILE_{col}' for col in range(7)], 'SELECT', 'RED_DROP', 'RED_HEIGHT', 'LAST',
              'RED_END', 'ERROR', 'READY', 'IDLE']
    f.save(output, ['INIT'], stages, ['TAIL', 'FINAL', 'HIDE'], 21)
    with TTFont(output) as font:
        lookups = font['GSUB'].table.LookupList.Lookup
        feature = next(r.Feature for r in font['GSUB'].table.FeatureList.FeatureRecord if r.FeatureTag == 'liga')

        def unwrap(subtable):
            return subtable.ExtSubTable if hasattr(subtable, 'ExtSubTable') else subtable

        targets = {}
        for index, name in enumerate(stages):
            wrapper = lookups[feature.LookupListIndex[1+index]]
            targets[name] = unwrap(wrapper.SubTable[0]).SubstLookupRecord[0].LookupListIndex
        for index, name in enumerate(['TAIL', 'FINAL', 'HIDE']):
            wrapper = lookups[feature.LookupListIndex[1+21*len(stages)+index]]
            targets[name] = unwrap(wrapper.SubTable[0]).SubstLookupRecord[0].LookupListIndex
        init_index = feature.LookupListIndex[0]

        gdef = font['GDEF'].table
        if not getattr(gdef, 'MarkGlyphSetsDef', None):
            gdef.MarkGlyphSetsDef = ot.MarkGlyphSetsDef(); gdef.MarkGlyphSetsDef.MarkSetTableFormat = 1
            gdef.MarkGlyphSetsDef.Coverage = []
        gdef.Version = 0x00010002

        def filtering(glyphs):
            sets = gdef.MarkGlyphSetsDef
            index = len(sets.Coverage)
            sets.Coverage.append(buildCoverage(glyphs, font.getReverseGlyphMap()))
            sets.MarkSetCount = len(sets.Coverage)
            return index

        def single(mapping):
            table = ot.SingleSubst(); table.mapping = mapping
            index = len(lookups); lookups.append(buildLookup([table], table='GSUB', extension=True))
            return index

        def record(slot, index):
            value = ot.SubstLookupRecord(); value.SequenceIndex = slot; value.LookupListIndex = index
            return value

        def outer(high_glyphs, inner_indices, mark_set):
            table = ot.ContextSubst(); table.Format = 2
            table.Coverage = buildCoverage(high_glyphs, font.getReverseGlyphMap())
            table.ClassDef = ot.ClassDef(); table.ClassDef.classDefs = {name: i+1 for i, name in enumerate(high_glyphs)}
            table.SubClassSet = [None]
            for index in inner_indices:
                rule = ot.SubClassRule(); rule.GlyphCount = 2; rule.Class = [0]
                rule.SubstLookupRecord = [record(1, index)]; rule.SubstCount = 1
                rules = ot.SubClassSet(); rules.SubClassRule = [rule]; rules.SubClassRuleCount = 1
                table.SubClassSet.append(rules)
            table.SubClassSetCount = len(table.SubClassSet)
            return buildLookup([table], flags=16, markFilterSet=mark_set, table='GSUB', extension=True)

        dispatch_filter = filtering([*high.values(), *low, *humans])
        encode_choices = [single(dict(zip(low, names))) for names in choices]

        def action_encoding(action, current_hi, current_lo):
            if action[0] == 'move':
                h, l = encoding(action[2]); return h, l, str(action[1])
            if action[0] == 'policy':
                pid = action[1]; return ('p', pid//POLICY_RADIX), pid%POLICY_RADIX, 'choose'
            return current_hi, current_lo, 'error'

        inners, dispatch_high = [], []
        for key in hi_keys:
            kind, block = key
            radix = RADIX if kind == 'b' else POLICY_RADIX
            count = min(radix, (len(branches) if kind == 'b' else len(policies))-block*radix) if kind != 't' else 1
            groups = range(7) if kind == 'b' else range(1)
            mapping = {}
            for human in groups:
                for lo in range(count):
                    if kind == 'b':
                        action = modes[branches[block*RADIX+lo]][1][human]
                        h, l, decision = action_encoding(action, key, lo)
                    else:
                        h, l, decision = key, lo, 'choose' if kind == 'p' else 'error'
                    mapping[choices[human][lo]] = [new_hi[h, decision], new_lo[l]]
            replacement = ot.MultipleSubst(); replacement.mapping = mapping
            setter = len(lookups); lookups.append(buildLookup([replacement], table='GSUB', extension=True))
            tables = []
            for human in groups:
                table = ot.ChainContextSubst(); table.Format = 3
                table.BacktrackCoverage = [buildCoverage([high[key]], font.getReverseGlyphMap())]
                table.BacktrackGlyphCount = 1
                table.InputCoverage = [buildCoverage(low[:count], font.getReverseGlyphMap())]
                table.InputGlyphCount = 1
                table.LookAheadCoverage = [buildCoverage([humans[human]] if kind == 'b' else humans, font.getReverseGlyphMap())]
                table.LookAheadGlyphCount = 1
                table.SubstLookupRecord = [record(0, encode_choices[human]), record(0, setter)]; table.SubstCount = 2
                tables.append(table)
            inners.append(len(lookups)); dispatch_high.append(high[key])
            lookups.append(buildLookup(tables, flags=16, markFilterSet=dispatch_filter, table='GSUB', extension=True))
        lookups[targets['DISPATCH']] = outer(dispatch_high, inners, dispatch_filter)
        profile_filter = filtering([*[high['p', i] for i in range(policy_blocks)], *copied_low])
        inners, selected_high = [], []
        for block in range(policy_blocks):
            table = ot.MultipleSubst()
            table.mapping = {
                copied_low[lo]: [profiles[profile_ids[col][tuple(policy[6*col:6*col+6])]] for col in range(7)]
                for lo, policy in enumerate(policies[block*POLICY_RADIX:(block+1)*POLICY_RADIX])}
            inners.append(len(lookups)); selected_high.append(high['p', block])
            lookups.append(buildLookup([table], table='GSUB', extension=True))
        lookups[targets['EXPAND_PROFILES']] = outer(selected_high, inners, profile_filter)
        for col in range(7):
            # At each explicit target, already-decoded earlier columns are
            # ignored marks. Thus the immediately preceding exposed glyph is
            # this column's height, even though profile IDs are shared.
            rank_filter = filtering([*heights[col], *profiles])
            tables = []
            # Full columns must also decode, to the unknown-rank sentinel.
            # Leaving a profile behind would obstruct the next column's
            # filtered height backtrack.
            for row in range(7):
                for begin in range(0, len(profile_vectors[col]), 4096):
                    end = min(begin+4096, len(profile_vectors[col]))
                    setter = single({profiles[i]: ranks[col][profile_vectors[col][i][row] if row < 6 else 42] for i in range(begin, end)})
                    table = ot.ChainContextSubst(); table.Format = 3
                    table.BacktrackCoverage = [buildCoverage([heights[col][row]], font.getReverseGlyphMap())]
                    table.BacktrackGlyphCount = 1
                    table.InputCoverage = [buildCoverage(profiles[begin:end], font.getReverseGlyphMap())]
                    table.InputGlyphCount = 1
                    table.LookAheadCoverage = []; table.LookAheadGlyphCount = 0
                    table.SubstLookupRecord = [record(0, setter)]; table.SubstCount = 1
                    tables.append(table)
            lookups[targets[f'READ_PROFILE_{col}']] = buildLookup(tables, flags=16,
                markFilterSet=rank_filter, table='GSUB', extension=True)

        # Drop the two scratch registers, replace low with the encoded reply
        # pair, then remove old high and restore scratch via NEW_LOW. The
        # temporary tape shrinks before expanding and never exceeds 64 glyphs.
        calls = [(P, 'CONSUME'), (P, 'FULL')]
        calls += [(i, 'HUMAN_DROP') for i in range(42)]
        calls += [(H+i, 'HUMAN_HEIGHT') for i in range(7)]
        calls += [(P, 'HUMAN_END'), (51, 'DROP_SCRATCH'), (51, 'DROP_SCRATCH'),
                  (49, 'DISPATCH'), (49, 'OLD_HIGH'), (58, 'DECISION'),
                  (49, 'NEW_HIGH'), (50, 'NEW_LOW'), (P, 'ACTIVATE'), (D, 'WIN'), (D, 'BLOCK')]
        calls += [(53+i, 'RESET_RANKS') for i in range(7)]
        calls += [(53, 'COPY_LOW')]+[(54, 'DROP_RANK_TAIL')]*6+[(49, 'EXPAND_PROFILES')]
        calls += [(53+i, f'READ_PROFILE_{i}') for i in range(7)]
        calls += [(D, 'SELECT')]+[(i, 'RED_DROP') for i in range(42)]
        calls += [(H+i, 'RED_HEIGHT') for i in range(7)]
        calls += [(LAST, 'LAST'), (P, 'RED_END'), (P, 'ERROR'), (P, 'READY'), (D, 'IDLE')]
        driver = ot.ContextSubst(); driver.Format = 3
        coverages = [list(values) for values in slots]
        coverages[P] = [parser['ready'], parser['win']]
        coverages.append(raw)
        driver.Coverage = [buildCoverage(values, font.getReverseGlyphMap()) for values in coverages]
        driver.GlyphCount = len(coverages)
        driver.SubstLookupRecord = [record(slot, targets[name]) for slot, name in calls]
        driver.SubstCount = len(calls)
        driver_index = len(lookups); lookups.append(buildLookup([driver], table='GSUB', extension=True))
        clocks = []
        for _ in range(21):
            clock = ot.ContextSubst(); clock.Format = 3; clock.GlyphCount = 1
            clock.Coverage = [buildCoverage(cells[0], font.getReverseGlyphMap())]
            clock.SubstLookupRecord = [record(0, driver_index)]; clock.SubstCount = 1
            clocks.append(len(lookups)); lookups.append(buildLookup([clock], table='GSUB', extension=True))
        final_clocks = []
        for name, coverage in [('TAIL', [parser['win'], parser['ready']]),
                                ('FINAL', list(parser.values())), ('HIDE', raw)]:
            clock = ot.ContextSubst(); clock.Format = 3; clock.GlyphCount = 1
            clock.Coverage = [buildCoverage(coverage, font.getReverseGlyphMap())]
            clock.SubstLookupRecord = [record(0, targets[name])]; clock.SubstCount = 1
            final_clocks.append(len(lookups)); lookups.append(buildLookup([clock], table='GSUB', extension=True))
        feature.LookupListIndex = [init_index, *clocks, *final_clocks]
        feature.LookupCount = len(feature.LookupListIndex)
        font['GSUB'].table.LookupList.LookupCount = len(lookups)
        # Every table is structured now, so remove unreachable construction
        # clocks and remap all nested references instead of keeping dummy IDs.
        def references(value):
            if isinstance(value, ot.SubstLookupRecord):
                yield value
            elif isinstance(value, (list, tuple)):
                for item in value:
                    yield from references(item)
            elif hasattr(value, '__dict__'):
                for item in vars(value).values():
                    yield from references(item)

        refs = {i: list(references(lookup)) for i, lookup in enumerate(lookups)}
        live, pending = set(), list(feature.LookupListIndex)
        while pending:
            index = pending.pop()
            if index in live:
                continue
            live.add(index)
            pending.extend(r.LookupListIndex for r in refs[index])
        remap = {old: new for new, old in enumerate(sorted(live))}
        for old in sorted(live):
            for r in refs[old]:
                r.LookupListIndex = remap[r.LookupListIndex]
        feature.LookupListIndex = [remap[index] for index in feature.LookupListIndex]
        lookups = [lookups[old] for old in sorted(live)]
        font['GSUB'].table.LookupList.Lookup = lookups
        font['GSUB'].table.LookupList.LookupCount = len(lookups)
        from fontTools.ttLib.tables.otBase import USE_HARFBUZZ_REPACKER
        font.cfg[USE_HARFBUZZ_REPACKER] = False
        if len(lookups) >= 65535:
            raise ValueError('OpenType lookup count exceeded')
        font.save(output)
        metadata = {'glyphs': len(font.getGlyphOrder()), 'lookups': len(lookups),
                    'controller_modes': len(modes), 'branch_modes': len(branches),
                    'priority_maps': len(policies), 'column_profiles': list(map(len, profile_vectors)),
                    'profile_glyphs': len(profiles), 'tape_registers': len(slots), 'turns': 21,
                    'abi': 'connect-four-independent-v1', 'max_driver_context': 64,
                    'driver_records': len(calls), 'mode_radix': RADIX, 'priority_radix': POLICY_RADIX,
                    'status_codes': STATUS, 'registers': slots}
        font.flavor = 'woff2'; font.save(Path(output).with_suffix('.woff2'))
    metadata.update(ttf_bytes=Path(output).stat().st_size, woff2_bytes=Path(output).with_suffix('.woff2').stat().st_size)
    Path(output).with_suffix('.independent.json').write_text(json.dumps(metadata, indent=2)+'\n')
    return metadata


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('controller', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    from policy_io import read_json
    result = build(read_json(args.controller), args.output)
    print(json.dumps({k: v for k, v in result.items() if k != 'registers'}, indent=2))
