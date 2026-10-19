# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Exact, independently generated strategy for THREE 3x3 Notakto boards.

No published strategy table or third-party code is embedded. We solve every
multiset of up to three symmetry-reduced boards by backward induction. The
eight single-board equivalence classes below are DERIVED for this fixed
three-board game; they are not claimed to replace the general 18-element
misere quotient for an arbitrary number of boards.
"""
from functools import lru_cache
from itertools import combinations_with_replacement

LINES = (0b000000111, 0b000111000, 0b111000000,
         0b001001001, 0b010010010, 0b100100100,
         0b100010001, 0b001010100)
DEAD = 512
MAX_MOVES = 27  # A conservative structural bound: three nine-cell boards.
START, END = "\ue000", "\ue001"


def dead(mask):
    return mask == DEAD or any(mask & line == line for line in LINES)


def transformations():
    maps = []
    for rotation in range(4):
        for reflect in range(2):
            mapping = []
            for cell in range(9):
                y, x = divmod(cell, 3)
                if reflect:
                    x = 2-x
                for _ in range(rotation):
                    x, y = 2-y, x
                mapping.append(3*y+x)
            maps.append(tuple(mapping))
    return tuple(maps)


TRANSFORMS = transformations()


def canonical(mask):
    if dead(mask):
        return DEAD
    return min(sum(1 << mapping[i] for i in range(9) if mask >> i & 1)
               for mapping in TRANSFORMS)


CANONICAL = tuple(canonical(mask) for mask in range(512))+(DEAD,)
BOARDS = tuple(sorted(set(CANONICAL)))
OPTIONS = {mask: tuple(sorted({CANONICAL[mask | (1 << i)] for i in range(9)
                              if not mask >> i & 1}))
           for mask in BOARDS if mask != DEAD}


@lru_cache(None)
def winning(position):
    """True if the player ABOUT TO MOVE wins; position is sorted/canonical.

    In misere play the empty sum is won by the player who did NOT make the
    last move. Thus all-dead is True, rather than the normal-play False.
    """
    if all(mask == DEAD for mask in position):
        return True
    for board, mask in enumerate(position):
        for successor in OPTIONS.get(mask, ()):
            child = tuple(sorted(position[:board]+position[board+1:]+(successor,)))
            if not winning(child):
                return True
    return False


@lru_cache(None)
def strategy_classes():
    """Derive and check single-board classes against every two-board context."""
    contexts = tuple(combinations_with_replacement(BOARDS, 2))
    signatures, by_signature = {}, {}
    for mask in BOARDS:
        signature = bytes(winning(tuple(sorted((mask, *context)))) for context in contexts)
        signatures[mask] = by_signature.setdefault(signature, len(by_signature))
    representatives = tuple(next(m for m in BOARDS if signatures[m] == i)
                            for i in range(len(by_signature)))
    classes = tuple(signatures[CANONICAL[m]] for m in range(512))
    # Check the simultaneous replacement of ALL three boards, not just each
    # board's individual signature against uncompressed contexts.
    for position in combinations_with_replacement(BOARDS, 3):
        reduced = tuple(sorted(representatives[signatures[m]] for m in position))
        assert winning(position) == winning(reduced)
    return classes, representatives


def choose(boards):
    """Lexicographically first winning move, or first legal move if losing."""
    fallback = None
    for board, mask in enumerate(boards):
        if dead(mask):
            continue
        for cell in range(9):
            if mask >> cell & 1:
                continue
            move = (board, cell)
            if fallback is None:
                fallback = move
            child = list(boards)
            child[board] |= 1 << cell
            if not winning(tuple(sorted(CANONICAL[m] for m in child))):
                return move
    return fallback


def replay(source):
    """Independent host oracle for tests; the playground never imports this."""
    boards, last = [0, 0, 0], None
    text = ''.join(c for c in source if c not in ' \t\r\n')
    if not text.startswith('b'):
        return boards, last, 'malformed'
    move = choose(boards)
    boards[move[0]] |= 1 << move[1]
    last = move
    text = text[1:]
    while text:
        if len(text) < 2 or text[0] not in 'ABC' or text[1] not in '123456789':
            return boards, last, 'malformed'
        board, cell = ord(text[0])-65, int(text[1])-1
        if dead(boards[board]) or boards[board] >> cell & 1:
            return boards, last, 'invalid'
        boards[board] |= 1 << cell
        if all(dead(mask) for mask in boards):
            return boards, last, 'computer_won'
        move = choose(boards)
        if move is None:
            return boards, last, 'internal'
        boards[move[0]] |= 1 << move[1]
        last = move
        if all(dead(mask) for mask in boards):
            return boards, last, 'human_won'
        text = text[2:]
    return boards, last, 'ready'
