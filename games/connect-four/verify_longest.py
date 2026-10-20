# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: GPL-3.0-only
"""Exhaustively find longest legal games under the pinned policy (Python only).

This strengthens the upstream strategy check with a maximum-length witness;
it does not constitute an exhaustive proof of the OpenType implementation.
"""
import json
import multiprocessing
from pathlib import Path
import sys
import time
HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'upstream/solution'))
import validate_solution as upstream
from reference import DIAGRAMS, OPENINGS, key, choose, board_of, replay, transition, drop, won


def leaf(job):
    entry, index, flip, prefix = job
    diagram = DIAGRAMS[index]
    if flip: diagram = [row[::-1] for row in diagram]
    memo = {}
    def red(board):
        k = tuple(tuple(row) for row in board)
        if k in memo: return memo[k]
        move = upstream.query_steady_state(board,diagram)
        assert move is not None
        x = move-1; y = upstream.col_height(board,x)
        assert y < 6
        board[y][x] = 1
        if upstream.makes_four(board,x,y,1):
            result = (1,'')
        else:
            candidates = []
            for xx in range(7):
                yy = upstream.col_height(board,xx)
                if yy == 6: continue
                board[yy][xx] = 2
                assert not upstream.makes_four(board,xx,yy,2)
                n, tail = red(board)
                candidates.append((2+n,str(xx+1)+tail))
                board[yy][xx] = 0
            assert candidates
            result = max(candidates)
        board[y][x] = 0
        memo[k] = result
        return result
    n, suffix = red([list(row) for row in entry])
    history = prefix+suffix
    board,status,last,mode,replies = replay(history)
    assert status == 'win'
    plies = sum(bool(v) for row in entry for v in row)+n
    assert plies == 1+2*len(history[1:])
    return plies,history,len(memo)


def opening_entries():
    # Traverse the actual canonical orientation transitions from b. Some
    # upstream spelling paths pass through symmetric boards and choose a
    # different mirrored continuation; use executable human histories here.
    queue = [(board_of('4'), ('branch', OPENINGS.index(''), 0), 'b')]
    seen, jobs, results = set(), [], []
    while queue:
        board, mode, history = queue.pop()
        ident = (key(board),mode)
        if ident in seen: continue
        seen.add(ident)
        for yellow in range(1,8):
            after = [row[:] for row in board]
            if drop(after,yellow-1,2) is None: continue
            assert not won(after,2)
            target = transition(mode,yellow)
            prefix = history+str(yellow)
            if target[0] == 'leaf':
                jobs.append((key(after),target[1],target[2],prefix))
                continue
            red = choose(after,target)
            if red is None or drop(after,red-1,1) is None:
                raise AssertionError('Strategy chose an unavailable column')
            if won(after,1): results.append((1+2*(len(prefix)-1),prefix,0))
            else: queue.append((after,target,prefix))
    return jobs, results, len(seen)


def main():
    started = time.perf_counter()
    jobs, results, opening_states = opening_entries()
    with multiprocessing.Pool(4) as pool: results += pool.map(leaf,jobs,chunksize=8)
    adversarial = sorted({(n,h) for n,h,_ in results},reverse=True)[:64]
    (HERE/'adversarial.json').write_text(json.dumps([h for n,h in adversarial],indent=2)+'\n')
    longest,history,_ = max(results)
    report = {'maximum_plies':longest,'human_history':history,'reachable_oriented_leaf_entries':len(jobs),'opening_states':opening_states,
              'memoized_positions':sum(r[2] for r in results),'seconds':round(time.perf_counter()-started,3)}
    (HERE/'longest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))

if __name__ == '__main__': main()
