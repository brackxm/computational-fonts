# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Serialize the hybrid policy for the independent coordinate-based checker."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from policy_io import source_bytes


def write_tape(policy, tape):
    if policy.get('format') != 'independent-c4-hybrid-v1' or policy.get('complete') is not True:
        raise ValueError('unsupported or incomplete certificate')
    nodes = policy['nodes']
    ids = {key: index for index, key in enumerate(sorted(nodes))}
    tape.write(f'C4HYBRID1 {len(ids)} {ids[policy["root"]]}\n')
    for key in sorted(ids):
        red, yellow, player = key.split('/')
        node = nodes[key]
        if set(node) == {'terminal'} and node['terminal'] == 'red':
            tape.write(f'{red} {yellow} {player} T\n')
        elif 'ranks' in node and 'edges' not in node:
            tape.write(f'{red} {yellow} {player} L '+ ' '.join(map(str, node['ranks']))+'\n')
        elif 'levels' in node and 'edges' not in node:
            tape.write(f'{red} {yellow} {player} P '+ ' '.join(map(str, node['levels']))+'\n')
        elif 'edges' in node and 'ranks' not in node:
            edges = node['edges']
            tape.write(f'{red} {yellow} {player} E {len(edges)}')
            for col, edge in sorted(edges.items()):
                tape.write(f' {col} {ids[edge["key"]]} {edge["flip"]}')
            tape.write('\n')
        else:
            raise ValueError('invalid node kind')


def check(path, executable, subgame=False):
    source = source_bytes(path)
    policy = json.loads(source)
    with tempfile.TemporaryFile(mode='w+t') as tape:
        write_tape(policy, tape)
        tape.seek(0)
        result = subprocess.run([str(executable), *(['--allow-subgame'] if subgame else [])],
                                stdin=tape, stdout=subprocess.PIPE, text=True, check=True)
    report = json.loads(result.stdout)
    report['certificate_sha256'] = hashlib.sha256(source).hexdigest()
    report['checker_source_sha256'] = hashlib.sha256(Path(__file__).with_suffix('.cpp').read_bytes()).hexdigest()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('policy', type=Path)
    parser.add_argument('--checker', type=Path)
    parser.add_argument('--export', type=Path, help='write the native certificate tape without running a checker')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--subgame', action='store_true')
    args = parser.parse_args()
    if args.export:
        with args.export.open('w') as tape:
            write_tape(json.loads(source_bytes(args.policy)), tape)
        return
    if not args.checker:
        parser.error('--checker is required unless --export is used')
    report = check(args.policy, args.checker, args.subgame)
    print(json.dumps(report, indent=2))
    if args.report:
        args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
