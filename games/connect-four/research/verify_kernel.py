# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Read back every policy table and compare real shaping with a game model.

The binary reader avoids materializing millions of FontTools rule objects.
"""
import argparse
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import random
import struct
import sys
import time

from fontTools.ttLib import TTFont
from runtime_reference import Reference, decode_shape
from kernel import STATUS, RADIX, POLICY_RADIX
from policy_io import read_json, source_bytes
import independent as c
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shaping import Shaper


class Reader:
    def __init__(self, path):
        with TTFont(path, lazy=True) as font:
            self.data = font.reader['GSUB']
            self.order = font.getGlyphOrder()
            self.mark_sets = [set(c.glyphs) for c in font['GDEF'].table.MarkGlyphSetsDef.Coverage]
        self.ids = {name: i for i, name in enumerate(self.order)}
        self.lookup_list = self.u16(8)

    def u16(self, offset):
        return struct.unpack_from('>H', self.data, offset)[0]

    def u32(self, offset):
        return struct.unpack_from('>I', self.data, offset)[0]

    def words(self, offset, count):
        return list(struct.unpack_from('>'+str(count)+'H', self.data, offset))

    @lru_cache(None)
    def subtables(self, index):
        lookup = self.lookup_list+self.u16(self.lookup_list+2+2*index)
        kind, flags, count = self.words(lookup, 3)
        result = []
        for offset in self.words(lookup+6, count):
            table = lookup+offset
            if kind == 7:
                actual = self.u16(table+2)
                table += self.u32(table+4)
            else:
                actual = kind
            result.append((actual, table))
        return result

    def coverage(self, offset):
        format, count = self.words(offset, 2)
        if format == 1:
            return self.words(offset+4, count)
        assert format == 2
        result = []
        for i in range(count):
            start, end, index = self.words(offset+4+6*i, 3)
            assert index == len(result)
            result.extend(range(start, end+1))
        return result

    @lru_cache(None)
    def classes(self, offset):
        format = self.u16(offset)
        if format == 1:
            start, count = self.words(offset+2, 2)
            return dict(zip(range(start, start+count), self.words(offset+6, count)))
        assert format == 2
        result = {}
        for i in range(self.u16(offset+2)):
            start, end, value = self.words(offset+4+6*i, 3)
            result.update((gid, value) for gid in range(start, end+1))
        return result

    def records(self, offset, count):
        return [tuple(self.words(offset+4*i, 2)) for i in range(count)]

    def outer(self, index, high_name):
        kind, table = self.subtables(index)[0]
        assert kind == 5 and self.u16(table) == 2
        cls = self.classes(table+self.u16(table+4))[self.ids[high_name]]
        rules = table+self.u16(table+8+2*cls)
        assert self.u16(rules) == 1
        rule = rules+self.u16(rules+2)
        assert self.words(rule, 3) == [2, 1, 0]
        assert self.u16(rule+6) == 1
        return self.u16(rule+8)

    @lru_cache(None)
    def single(self, index, input_name):
        gid = self.ids[input_name]
        for kind, table in self.subtables(index):
            assert kind == 1
            coverage = self.coverage(table+self.u16(table+2))
            if gid not in coverage:
                continue
            if self.u16(table) == 1:
                out = (gid+self.u16(table+4)) & 65535
            else:
                assert self.u16(table) == 2
                out = self.u16(table+6+2*coverage.index(gid))
            return self.order[out]
        raise AssertionError(('missing single substitution', index, input_name))

    def filter_names(self, index):
        lookup = self.lookup_list+self.u16(self.lookup_list+2+2*index)
        _, flags, count = self.words(lookup, 3)
        assert flags == 16
        return self.mark_sets[self.u16(lookup+6+2*count)]

    def chains(self, index):
        for kind, table in self.subtables(index):
            assert kind == 6 and self.u16(table) == 1
            coverage = self.coverage(table+self.u16(table+2))
            for i, gid in enumerate(coverage):
                rules = table+self.u16(table+6+2*i)
                for offset in self.words(rules+2, self.u16(rules)):
                    yield gid, self.chain_rule(rules+offset)

    @lru_cache(None)
    def multiples(self, index):
        result = {}
        for kind, table in self.subtables(index):
            assert kind == 2 and self.u16(table) == 1
            coverage = self.coverage(table+self.u16(table+2))
            for i, gid in enumerate(coverage):
                sequence = table+self.u16(table+6+2*i)
                result[gid] = [self.order[g] for g in self.words(sequence+2, self.u16(sequence))]
        return result

    def multiple(self, index, input_name):
        return self.multiples(index)[self.ids[input_name]]

    def chain_rule(self, offset):
        p = offset
        count = self.u16(p); back = self.words(p+2, count); p += 2+2*count
        count = self.u16(p); inputs = self.words(p+2, count-1); p += 2+2*(count-1)
        count = self.u16(p); ahead = self.words(p+2, count); p += 2+2*count
        count = self.u16(p)
        return back, inputs, ahead, self.records(p+2, count)

    def dispatch(self, index, low, human, high_name):
        for kind, table in self.subtables(index):
            assert kind == 6 and self.u16(table) == 3
            assert self.u16(table+2) == 1
            assert self.coverage(table+self.u16(table+4)) == [self.ids[high_name]]
            assert self.u16(table+6) == 1
            coverage = self.coverage(table+self.u16(table+8))
            assert self.u16(table+10) == 1
            ahead = self.coverage(table+self.u16(table+12))
            if self.ids[f'r_p_h{human}'] not in ahead:
                continue
            assert self.words(table+14, 2) == [2, 0]
            assert self.u16(table+20) == 0
            assert self.ids[f'r_lo_{low}'] in coverage
            encoded = self.single(self.u16(table+18), f'r_lo_{low}')
            expected_human = human-1 if len(ahead) == 1 else 0
            assert encoded == f'r_choice_{expected_human}_{low}'
            output = self.multiple(self.u16(table+22), encoded)
            assert len(output) == 2
            hi, decision = output[0].rsplit('_', 1)
            return hi, output[1], 'r_d_'+decision, 'r_p_active'
        raise AssertionError('missing dispatch rule')

    def driver(self):
        feature_list = self.u16(6)
        for i in range(self.u16(feature_list)):
            record = feature_list+2+6*i
            if self.data[record:record+4] == b'liga':
                feature = feature_list+self.u16(record+4)
                indices = self.words(feature+4, self.u16(feature+2))
                break
        kind, clock = self.subtables(indices[1])[0]
        assert kind == 5 and self.words(clock, 3) == [3, 1, 1]
        driver_index = self.u16(clock+10)
        kind, driver = self.subtables(driver_index)[0]
        format, glyphs, count = self.words(driver, 3)
        assert (kind, format, glyphs, count) == (5, 3, 64, 139)
        records = self.records(driver+6+2*glyphs, count)
        assert [r[0] for r in records[52:60]] == [51, 51, 49, 49, 58, 49, 50, 62]
        return records


def verify_tables(path, controller):
    reader = Reader(path)
    records = reader.driver()
    dispatch = records[54][1]
    branches = [i for i, mode in enumerate(controller['modes']) if mode[0] == 'branch']
    branch_ids = {mode: i for i, mode in enumerate(branches)}

    def encoding(index):
        mode = controller['modes'][index]
        if mode[0] == 'branch':
            value = branch_ids[index]
            return f'r_next_hi_b_{value//RADIX}', f'r_next_lo_{value%RADIX}'
        if mode[0] == 'policy':
            value = mode[1]
            return f'r_next_hi_p_{value//POLICY_RADIX}', f'r_next_lo_{value%POLICY_RADIX}'
        return 'r_next_hi_t_0', 'r_next_lo_0'

    checked_dispatch = 0
    for index, mode_index in enumerate(branches):
        high, low = index//RADIX, index%RADIX
        inner = reader.outer(dispatch, f'r_hi_b_{high}')
        for human, action in enumerate(controller['modes'][mode_index][1], 1):
            if action[0] == 'move':
                hi, lo = encoding(action[2]); decision = f'r_d_{action[1]}'
            elif action[0] == 'policy':
                value = action[1]; hi, lo = f'r_next_hi_p_{value//POLICY_RADIX}', f'r_next_lo_{value%POLICY_RADIX}'; decision = 'r_d_choose'
            else:
                hi, lo, decision = f'r_next_hi_b_{high}', f'r_next_lo_{low}', 'r_d_error'
            assert reader.dispatch(inner, low, human, f'r_hi_b_{high}') == (hi, lo, decision, 'r_p_active'), (index, human)
            checked_dispatch += 1
    branch_dispatch = checked_dispatch
    policy_dispatch = 0
    for index in range(len(controller['policies'])):
        block, low = divmod(index, POLICY_RADIX)
        hi = f'r_hi_p_{block}'
        inner = reader.outer(dispatch, hi)
        for human in range(1, 8):
            assert reader.dispatch(inner, low, human, hi) == (f'r_next_hi_p_{block}', f'r_next_lo_{low}', 'r_d_choose', 'r_p_active')
            policy_dispatch += 1
    inner = reader.outer(dispatch, 'r_hi_t_0')
    for human in range(1, 8):
        assert reader.dispatch(inner, 0, human, 'r_hi_t_0') == ('r_next_hi_t_0', 'r_next_lo_0', 'r_d_error', 'r_p_active')
    checked_dispatch += policy_dispatch+7
    # Verify extraction of every encoded decision and restoration of the fixed
    # register layout, including combinations unreachable in ordinary games.
    kind, table = reader.subtables(records[56][1])[0]
    assert kind == 6 and reader.u16(table) == 2
    back_classes = reader.classes(table+reader.u16(table+4))
    input_classes = reader.classes(table+reader.u16(table+6))
    ahead_classes = reader.classes(table+reader.u16(table+8))
    assert input_classes[reader.ids['r_d_idle']] == 1
    assert all(ahead_classes[reader.ids[f'r_p_h{i}']] == 1 for i in range(1, 8))
    rules = table+reader.u16(table+14)
    decoded_actions = {}
    for offset in reader.words(rules+2, reader.u16(rules)):
        back, inputs, ahead, rec = reader.chain_rule(rules+offset)
        assert len(back) == 1 and inputs == [] and ahead == [1]
        assert len(rec) == 1 and rec[0][0] == 0
        decoded_actions[back[0]] = reader.single(rec[0][1], 'r_d_idle')
    for name in reader.order:
        if not name.startswith('r_next_hi_') or name == 'r_next_hi_unknown':
            continue
        action = name.rsplit('_', 1)[1]
        assert decoded_actions[back_classes[reader.ids[name]]] == 'r_d_'+action
        assert reader.single(records[57][1], name) == name.rsplit('_', 1)[0].replace('r_next_hi_', 'r_hi_')
    for low in range(256):
        assert reader.multiple(records[58][1], f'r_next_lo_{low}') == [f'r_lo_{low}', 'r_next_hi_unknown', 'r_next_lo_unknown']
    for human in range(1, 8):
        assert reader.single(records[59][1], f'r_p_h{human}') == 'r_p_active'
    # Decode the serialized MultipleSubst profile vectors and height-specific
    # SingleSubst mappings, then compare every original 42-cell priority.
    assert [r[0] for r in records[69:84]] == [53, *([54]*6), 49, *range(53, 60)]
    guards = [reader.ids['r_d_choose'], reader.ids['r_p_active']]
    copied = set()
    for gid, (back, inputs, ahead, rec) in reader.chains(records[69][1]):
        assert gid == reader.ids['r_rank_0_42'] and inputs == [] and ahead == guards
        assert len(back) == 1 and len(rec) == 1 and rec[0][0] == 0
        lo = next(i for i in range(256) if back == [reader.ids[f'r_lo_{i}']])
        assert reader.single(rec[0][1], 'r_rank_0_42') == f'r_copy_lo_{lo}'
        copied.add(lo)
    assert copied == set(range(256))
    assert len({r[1] for r in records[70:76]}) == 1
    dropped = set()
    for gid, (back, inputs, ahead, rec) in reader.chains(records[70][1]):
        col = next(c for c in range(1, 7) if gid == reader.ids[f'r_rank_{c}_42'])
        assert back == [] and inputs == []
        assert ahead == [reader.ids[f'r_rank_{c}_42'] for c in range(col+1, 7)]+guards
        assert len(rec) == 1 and rec[0][0] == 0
        assert reader.multiple(rec[0][1], f'r_rank_{col}_42') == []
        dropped.add(col)
    assert dropped == set(range(1, 7))
    assert reader.filter_names(records[69][1]) == {f'r_lo_{i}' for i in range(256)} | {'r_rank_0_42', 'r_d_choose', 'r_p_active'}
    assert reader.filter_names(records[70][1]) == {f'r_rank_{c}_42' for c in range(1, 7)} | {'r_d_choose', 'r_p_active'}
    assert reader.filter_names(records[76][1]) == {f'r_hi_p_{i}' for i in range((len(controller['policies'])+255)//256)} | {f'r_copy_lo_{i}' for i in range(256)}
    profiles = []
    for block in range((len(controller['policies'])+POLICY_RADIX-1)//POLICY_RADIX):
        inner = reader.outer(records[76][1], f'r_hi_p_{block}')
        kind, table = reader.subtables(inner)[0]
        assert kind == 2 and reader.u16(table) == 1
        coverage = reader.coverage(table+reader.u16(table+2))
        for low, gid in enumerate(coverage):
            assert gid == reader.ids[f'r_copy_lo_{low}']
            sequence = table+reader.u16(table+6+2*low)
            assert reader.u16(sequence) == 7
            profiles.append(reader.words(sequence+2, 7))
    assert len(profiles) == len(controller['policies'])
    decoded = []
    for col in range(7):
        assert reader.filter_names(records[77+col][1]) == {f'r_h{col}_{r}' for r in range(7)} | {name for name in reader.order if name.startswith('r_profile_')}
        rows = [{} for _ in range(7)]
        for kind, table in reader.subtables(records[77+col][1]):
            assert kind == 6 and reader.u16(table) == 3
            assert reader.u16(table+2) == 1
            back = reader.coverage(table+reader.u16(table+4))
            assert len(back) == 1
            row = next(r for r in range(7) if back == [reader.ids[f'r_h{col}_{r}']])
            assert reader.u16(table+6) == 1
            coverage = reader.coverage(table+reader.u16(table+8))
            assert reader.words(table+10, 3) == [0, 1, 0]
            setter = reader.u16(table+16)
            # Parse the whole SingleSubst once, avoiding a quadratic coverage scan.
            for skind, stable in reader.subtables(setter):
                assert skind == 1 and reader.u16(stable) == 2
                inputs = reader.coverage(stable+reader.u16(stable+2))
                outputs = reader.words(stable+6, reader.u16(stable+4))
                assert inputs == coverage
                for src, dst in zip(inputs, outputs):
                    assert src not in rows[row]
                    rows[row][src] = reader.order[dst]
        assert all(value == f'r_rank_{col}_42' for value in rows[6].values())
        assert set(rows[6]) == set(rows[0])
        decoded.append(rows)
    checked_ranks = 0
    for policy, vector in zip(controller['policies'], profiles):
        for col in range(7):
            for row in range(6):
                assert decoded[col][row][vector[col]] == f'r_rank_{col}_{policy[6*col+row]}'
                checked_ranks += 1
    return {'dispatch_entries': checked_dispatch, 'branch_dispatch_entries': branch_dispatch,
            'policy_dispatch_entries': policy_dispatch, 'terminal_dispatch_entries': 7,
            'priority_entries': checked_ranks,
            'profile_vectors': len(profiles),
            'column_profiles': [len(rows[0]) for rows in decoded]}


def verify_histories(path, controller, witness, games):
    reference, shaper = Reference(controller), Shaper(path)
    rng = random.Random(20261024)
    count, timings = 0, []

    def check(source, transport=False):
        nonlocal count
        expected = reference.replay(source)
        begin = time.perf_counter()
        shaped = shaper.run(source, transport=transport)
        timings.append((time.perf_counter()-begin)*1000)
        actual = decode_shape(shaped)
        wanted = expected.red, expected.yellow, expected.last, 1000+STATUS[expected.status]
        assert actual == wanted, (source, actual, wanted, [g[0] for g in shaped[-15:]])
        assert len(shaped) == 64, (source, 'incomplete register tape')
        count += 1
        return expected

    try:
        for source in ('b', 'b1', 'b135', 'b4444', 'b!', 'x', 'bλ', 'b🙂', 'b\ue162', 'b\n'):
            check(source, transport=True)
        for i in range(1, len(witness)+1):
            check(witness[:i])
        assert check(witness).status == 'win'
        check(witness+'1'); check(witness+'!')
        for game in range(games):
            source = 'b'
            while True:
                state = check(source)
                if state.status != 'ready':
                    assert state.status == 'win', (source, state.status)
                    break
                if game % 10 == 0:
                    for col in range(7):
                        if col not in c.legal(state.red, state.yellow):
                            check(source+str(col+1)+'123')
                source += str(rng.choice(c.legal(state.red, state.yellow))+1)
        assert sum(g[1] for g in shaper.run('b', enabled=False)) == 0
        version = shaper.version
    finally:
        shaper.close()
    timings.sort()
    return {'history_shapes': count, 'complete_games': games, 'harfbuzz': version,
            'median_ms': timings[len(timings)//2], 'max_ms': max(timings), 'longest_human_history': witness}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('font', type=Path)
    parser.add_argument('--controller', type=Path, required=True)
    parser.add_argument('--proof', type=Path, required=True)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--games', type=int, default=500)
    args = parser.parse_args()
    controller = read_json(args.controller)
    proof = json.loads(args.proof.read_text())
    report = {'tables': verify_tables(args.font, controller)}
    print(json.dumps(report), flush=True)
    report['shaping'] = verify_histories(args.font, controller, proof['longest_human_history'], args.games)
    report['font_sha256'] = hashlib.sha256(args.font.read_bytes()).hexdigest()
    report['controller_sha256'] = hashlib.sha256(source_bytes(args.controller)).hexdigest()
    report['certificate_sha256'] = proof['certificate_sha256']
    print(json.dumps(report, indent=2))
    if args.report:
        args.report.write_text(json.dumps(report, indent=2)+'\n')
