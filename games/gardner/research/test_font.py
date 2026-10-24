# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Verify the packaged font, legal replays, clock boundaries and timing gates."""
import argparse
import lzma
import hashlib
import json
from pathlib import Path
import shutil
import statistics
import struct
import subprocess
import tempfile
import time

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable
import uharfbuzz as hb

from build import HERE, check_inputs, sha256
from runtime import Font, Policy, decode, model, move_text
from test_dictionary import check_dictionary


def expected(policy, board, clock):
    if clock >= 150 or model.dead(board):
        return board, None, 7, clock
    bound, code = policy.query(board)
    if bound == 250:
        assert not model.legal(board, True) and not model.checked(board, True) or model.dead(board)
        return board, None, 7, clock
    move = move_text(code)
    legal = model.legal(board, True)
    assert move in legal
    if clock >= 100 and bound != 149 or clock == 99 and bound != 149 and model.tick(board, move, clock):
        return board, None, 7, clock
    after = legal[move]
    counter = model.tick(board, move, clock)
    status = 1 if model.legal(after, False) else 2 if model.checked(after, False) else 7
    if model.dead(after) or counter >= 150 and status != 2:
        status = 7
    return after, move[2:4], status, counter


def check_history(font, policy, positions):
    board = model.legal(model.INITIAL, True)['a2a3']
    source, clock, checks = 'b', 0, 0
    for position in positions:
        following = position['source']
        if following != source:
            assert following.startswith(source) and following.endswith(';')
            move = following[len(source):-1].lower()
            child = model.legal(board, False)[move]
            clock = model.tick(board, move, clock)
            board, last, status, clock = expected(policy, child, clock)
            assert (board, last, status) == (position['board'], position['last'], position['status'])
            assert clock == position['quietClock']
        actual = font.shape(following)
        assert actual == (position['board'], position['last'], position['status']), following
        source, checks = following, checks + 1
    return checks


def check_boundaries(path, font, policy, directory):
    alias_path = directory / 'seed.ttf'
    tags = ['GSUB', 'GDEF', 'glyf', 'hmtx']
    with TTFont(path, lazy=True) as source:
        before = {tag: hashlib.sha256(source.getTableData(tag)).hexdigest() for tag in tags}
        alias = CmapSubtable.newSubtable(12)
        alias.platformID, alias.platEncID, alias.language = 0, 4, 0
        alias.cmap = {0x100000+i: name for i, name in enumerate(source.getGlyphOrder())}
        source['cmap'].tables.append(alias)
        source.save(alias_path)
    with TTFont(alias_path, lazy=True) as source:
        assert all(hashlib.sha256(source.getTableData(tag)).hexdigest() == digest for tag, digest in before.items())
    seeded = hb.Font(hb.Face(alias_path.read_bytes()))
    ids = {name: i for i, name in enumerate(font.order)}
    data = (HERE / 'inputs/boundaries.records29').read_bytes()
    assert len(data) % 29 == 0
    checks = 0
    for offset in range(0, len(data), 29):
        board = data[offset:offset+25].decode()
        for clock in [0, 98, 99, 100, 149, 150]:
            names = ['board', 'r_state_header', 'r_last_none']
            for bank in ['work', 'cell']:
                names += [f'r_{bank}_{i}_{piece if piece != "." else "empty"}' for i, piece in enumerate(board)]
            names += ['r_count_' + str(clock), 'input_98', 'end']
            buffer = hb.Buffer()
            buffer.add_str(''.join(chr(0x100000+ids[name]) for name in names))
            buffer.direction, buffer.script = 'ltr', 'Latn'
            hb.shape(seeded, buffer, {'liga': True})
            actual = decode([font.order[g.codepoint] for g in buffer.glyph_infos])
            assert actual == expected(policy, board, clock)[:3], (board, clock, actual)
            checks += 1
    return checks


def timings(font, position):
    samples = []
    for nonce in range(1, 21):
        before = time.perf_counter()
        actual = font.shape(position['source'], nonce)
        samples.append((time.perf_counter() - before) * 1000)
        assert actual == (position['board'], position['last'], position['status'])
    return dict(median_ms=statistics.median(samples), p95_ms=sorted(samples)[19], max_ms=max(samples))


def check_bad_trees(compiler, header, directory):
    # Reject corrupt child references before bank layout dereferences them.
    header = bytearray(header)
    struct.pack_into('<4I', header, 4, 1, 1, 1, 0)
    cases = [
        ('feature', 192, -1, 'bad node feature'),
        ('forward', 0, 0, 'non-postorder DAG'),
        ('leaf', 0, -2, 'bad leaf label'),
        ('missing', 0, -(2**31), 'missing binary edge'),
    ]
    for name, feature, child, error in cases:
        tree = directory / (name + '.tree')
        tree.write_bytes(header + struct.pack('<I3i', 250*3125, feature, child, -1))
        result = subprocess.run([str(compiler.resolve()), str(tree), str(directory / name),
                                 '6404', 'game', 'unused.gamepack', 'unused.gsub'],
                                capture_output=True, text=True)
        assert result.returncode == 1 and error in result.stderr, (name, result)
    return len(cases)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--font', type=Path, default=HERE / 'gardner-research.ttf')
    parser.add_argument('--build-dir', type=Path, default=HERE / 'build')
    args = parser.parse_args()
    manifest = json.loads((HERE / 'manifest.json').read_text())
    check_inputs(manifest)
    assert sha256(args.font) == manifest['font_sha256']
    assert args.font.stat().st_size <= manifest['limits']['font_bytes']
    with TTFont(args.font, lazy=True) as font:
        assert len(font.getGlyphOrder()) <= manifest['limits']['glyphs']
    with tempfile.TemporaryDirectory(prefix='gardner-research-') as directory:
        directory = Path(directory)
        tree = directory / 'policy.tree'
        with lzma.open(HERE / 'inputs/policy.tree.xz', 'rb') as source, tree.open('wb') as output:
            shutil.copyfileobj(source, output)
        assert sha256(tree) == manifest['policy_tree_sha256']
        policy, font = Policy(tree), Font(args.font)
        bad_trees = check_bad_trees(args.build_dir / 'binary-font', policy.data[:80], directory)
        assert struct.unpack_from('<I', policy.data, 4)[0] == manifest['font_reachable_rows']
        # Pin each added clock-zero continuation and exercise it in the boundary fixture.
        data = (HERE / 'inputs/boundaries.records29').read_bytes()
        boundary_boards = {data[i:i+25].decode() for i in range(0, len(data), 29)}
        continuations = [
            ('f00', 'c3b4'), ('f01', 'b2c3'), ('f02', 'a1a3'),
            ('f03', 'e1d1'), ('f04', 'a1a3'), ('f05', 'b2c3'),
            ('f12', 'a3b1'), ('f13', 'a3b1'), ('f14', 'd2e3'),
            ('f15', 'b1a3'), ('f18', 'b1c3'), ('f19', 'a1a3'),
        ]
        earlier = [('f20', 'b2a3'), ('f23', 'e2e3'), ('f22', 'c3b5')]
        for name, move in earlier + continuations:
            entry = manifest[name]
            assert entry['safe_entry_clock'] == 0
            bound, code = policy.query(entry['board'])
            assert (bound, move_text(code)) == (150, move)
            assert entry['board'] in boundary_boards
        # Pin every first Black reply for the extended frontier fixture.
        for name, move in continuations:
            after = model.legal(manifest[name]['board'], True)[move]
            assert set(model.legal(after, False).values()) <= boundary_boards
        first = model.legal(model.INITIAL, True)['a2a3']
        assert font.shape('b') == (first, 'a3', 1)
        for move in ['B4A3', 'B4B3']:
            assert font.shape('b' + move + ';')[2] == 6
        assert font.shape('bA1A1;')[2] == 4
        for source in ['bgarbage', 'garbage', 'bb', 'bB4', 'b🙂', 'bgarbageB5C3;b']:
            assert font.shape(source)[2] == 5, source
        assert font.shape('bB4A3;bgarbageB5C3;')[2] == 6
        assert font.shape('bA1A1;B5C3;bgarbage')[2] == 4
        for suffix in ['b', 'B5C3;', 'bB5C3;', 'garbage', ' ', '🙂']:
            assert font.shape('bgarbage' + suffix * 12)[2] == 5
        replay = json.loads((HERE / 'inputs/replay.json').read_text())
        checks = check_history(font, policy, replay['positions'])
        for game in json.loads((HERE / 'inputs/games.json').read_text()):
            checks += check_history(font, policy, game)
        boundaries = check_boundaries(args.font, font, policy, directory)
        target = replay['positions'][replay['benchmarkIndex']]
        assert target['livePlies'] == 151 and target['status'] == 1
        full, twenty = timings(font, target), timings(font, replay['positions'][20])
        assert full['max_ms'] <= manifest['limits']['live_150_ply_max_ms'], full
        assert twenty['p95_ms'] <= manifest['limits']['twenty_reply_p95_ms'], twenty
        # Exhaust every serialized dispatcher transition, using fresh build metadata.
        compiler = directory / 'check-dispatch'
        subprocess.run(['clang++', '-std=c++17', '-O3', str(HERE / 'compiler/check_dispatch.cpp'), '-o', str(compiler)], check=True)
        result = subprocess.run([str(compiler), str(args.font.resolve()), str(tree),
                                 str((args.build_dir / 'gardner-research.addresses').resolve()),
                                 str((args.build_dir / 'gardner-research.dispatch.bin').resolve())], check=True, capture_output=True, text=True)
        dispatch = json.loads(result.stdout)
        assert dispatch['node_value_pairs'] == 2 * struct.unpack_from('<I', policy.data, 8)[0]
        dictionary = check_dictionary(args.font, tree, args.build_dir / 'gardner-research', directory)
    print(json.dumps(dict(status='pass',font_sha256=manifest['font_sha256'],history_checks=checks,
                          boundary_checks=boundaries,bad_tree_checks=bad_trees,dispatch=dispatch,dictionary=dictionary,
                          live150=full,twenty_reply=twenty,
                          proof_searches=0), indent=2))


if __name__ == '__main__':
    main()
