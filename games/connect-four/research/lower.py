# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Share compatible landing-cell orders and minimize the font controller."""
from functools import lru_cache
from collections import Counter
import json
from pathlib import Path
import subprocess
import tempfile
import hashlib
from policy_io import source_bytes

import independent as c


def column_levels(policy):
    """Coalesce consecutive alternatives in one column; preserve comparisons."""
    result = [0]*42
    previous, level = -1, -1
    for cell in sorted(range(42), key=lambda i: policy[i]):
        column = cell//6
        if column != previous:
            previous, level = column, level+1
        result[cell] = level
    return result


def lower(certificate, grouper):
    nodes = certificate['nodes']
    leaves = sorted(key for key, node in nodes.items() if 'ranks' in node)
    entries = []
    for key in leaves:
        red, yellow, player = key.split('/')
        red, yellow = int(red, 16), int(yellow, 16)
        ranks = nodes[key]['ranks']
        empty = [6*col+row for col in range(7) for row in range(6)
                 if not (red | yellow) & (1 << (7*col+row))]
        original = sorted(empty, key=lambda cell: ranks[cell])
        flipped = tuple(ranks[6*(6-col)+row] for col in range(7) for row in range(6))
        entries += [(key, 0, tuple(ranks), original),
                    (key, 1, flipped, [6*(6-cell//6)+cell%6 for cell in original])]
    frequencies = Counter(entry[2] for entry in entries)
    entries.sort(key=lambda entry: (-frequencies[entry[2]], entry[2], entry[0], entry[1]))
    chains = [entry[3] for entry in entries]
    with tempfile.TemporaryFile(mode='w+t') as tape:
        tape.write(str(len(chains))+'\n')
        for chain in chains:
            tape.write(str(len(chain))+' '+ ' '.join(map(str, chain))+'\n')
        tape.seek(0)
        result = subprocess.run([str(grouper)], stdin=tape, stdout=subprocess.PIPE, text=True, check=True)
    grouped = json.loads(result.stdout)
    assignments, policies = grouped['assignments'], grouped['policies']
    # Adjacent cells from one column can share a level: only one is playable
    # at a time. Preserve every cross-column comparison exactly.
    policies = [column_levels(policy) for policy in policies]
    for chain, group in zip(chains, assignments):
        # An independent preservation check: all future landing cells are a
        # subset of the entry's empty cells. Only comparisons between
        # different columns can influence a legal choice.
        if any(policies[group][a] >= policies[group][b]
               for i, a in enumerate(chain) for b in chain[i+1:] if a//6 != b//6):
            raise ValueError('merged policy changes a possible landing-cell ordering')
    policy_ids = {(entry[0], entry[1]): assignments[i] for i, entry in enumerate(entries)}
    modes, mode_ids = [], {}

    def intern(signature):
        if signature not in mode_ids:
            mode_ids[signature] = len(modes)
            modes.append(signature)
        return mode_ids[signature]

    @lru_cache(None)
    def red_action(key, flip):
        node = nodes[key]
        if 'ranks' in node:
            return ('policy', policy_ids[key, flip])
        if 'terminal' in node:
            raise ValueError('Red terminal reached before a prescribed reply')
        (column, edge), = node['edges'].items()
        col = int(column)
        return ('move', 8-col if flip else col, yellow_mode(edge['key'], flip ^ edge['flip']))

    @lru_cache(None)
    def yellow_mode(key, flip):
        node = nodes[key]
        if 'ranks' in node:
            return intern(('policy', policy_ids[key, flip]))
        if 'terminal' in node:
            return intern(('terminal',))
        options = []
        for actual in range(1, 8):
            canonical = 8-actual if flip else actual
            edge = node['edges'].get(str(canonical))
            options.append(red_action(edge['key'], flip ^ edge['flip']) if edge else ('invalid',))
        return intern(('branch', tuple(options)))

    if certificate['root'] in nodes:
        root = certificate['root']
        if root.endswith('/1'):
            first = red_action(root, 0)
        else:
            first = ('start', yellow_mode(root, 0))
    else:
        first = None
        # A partial frontier can be inspected for size; it cannot build a font.
        for key in nodes:
            if key.endswith('/2'):
                yellow_mode(key, 0)
                yellow_mode(key, 1)
    return {'format': 'independent-c4-controller-v1', 'complete': certificate.get('complete') is True,
            'initial_action': first, 'policies': policies, 'modes': modes,
            'source_vertices': len(nodes), 'source_leaf_maps': len(leaves),
            'merged_leaf_maps': len(policies), 'controller_modes': len(modes)}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('certificate', type=Path)
    parser.add_argument('--grouper', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    source = source_bytes(args.certificate)
    result = lower(json.loads(source), args.grouper)
    result['certificate_sha256'] = hashlib.sha256(source).hexdigest()
    if args.output:
        args.output.write_text(json.dumps(result, separators=(',', ':'))+'\n')
    print({k: v for k, v in result.items() if k not in ('policies', 'modes')})
