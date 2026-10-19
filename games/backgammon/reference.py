# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0

"""Independent test oracle; never used by the builder or browser playground.

This parses the documented subset in Python and replays explicit transfers.
It deliberately does not check backgammon legality.
"""

import re

MAX_TURNS = 128


class ReplayError(ValueError):
    def __init__(self, status):
        super().__init__(status)
        self.status = status


def replay(source):
    """Return (register dictionary, status); partial boards are not returned."""
    source = re.sub(r"[ \t\r\n]", "", source)
    board = {c: 0 for c in "abcdefghijklmnopqrstuvwx"}
    board.update(a=-2, f=5, h=3, l=-5, m=5, q=-3, s=-5, x=2)
    state = {**board, "barW": 0, "barB": 0, "offW": 0, "offB": 0,
             "die1": "0", "die2": "0", "turn": 0}
    index = 0

    def fail(status="malformed"):
        raise ReplayError(status)

    def expect(text):
        nonlocal index
        if not source.startswith(text, index):
            fail()
        index += len(text)

    try:
        expect("(;")
        seen = set()
        properties = {"GM": "6", "FF": "4", "CA": "UTF-8"}
        while source[index:index+1].isupper() and source[index:index+1] not in ("W", "B"):
            match = re.match(r"([A-Z]+)\[([^\]]*)\]", source[index:])
            if not match:
                fail("unsupported")
            prop, value = match.groups()
            if prop not in properties or value != properties[prop] or prop in seen:
                fail("unsupported")
            seen.add(prop)
            index += len(match.group())
        # Empty root may be followed by a move node or by the closing tree.
        if source[index:index+1] == ";":
            index += 1
            if source[index:index+1] not in ("W", "B"):
                fail("unsupported" if source[index:index+1].isupper() else "malformed")
        while source[index:index+1] in ("W", "B"):
            player = source[index]
            index += 1
            expect("[")
            if state["turn"] == MAX_TURNS:
                fail("limit")
            state["turn"] += 1
            value = re.match(r"([1-6])([1-6])((?:[a-y][a-xz]){0,4})\]", source[index:])
            if not value:
                fail("unsupported" if source[index:index+1].islower() else "malformed")
            d1, d2, pairs = value.groups()
            state["die1"], state["die2"] = player+d1, player+d2
            sign = 1 if player == "W" else -1
            opponent = "B" if player == "W" else "W"
            for start, end in zip(pairs[::2], pairs[1::2]):
                if start == "y":
                    if state["bar"+player] == 0:
                        fail("state_error")
                    state["bar"+player] -= 1
                else:
                    if state[start]*sign <= 0:
                        fail("state_error")
                    state[start] -= sign
                if end == "z":
                    state["off"+player] += 1
                else:
                    if state[end]*sign < -1:
                        fail("state_error")
                    if state[end] == -sign:
                        state["bar"+opponent] += 1
                        state[end] = 0
                    state[end] += sign
            index += len(value.group())
            if source[index:index+1] != ";":
                break
            index += 1
            if source[index:index+1] not in ("W", "B"):
                fail("unsupported" if source[index:index+1].isupper() else "malformed")
        if source[index:index+1].isupper() or source[index:index+1] == "(":
            fail("unsupported")
        expect(")")
        if index != len(source):
            fail("unsupported" if source[index:index+1] == "(" else "malformed")
        return state, "complete"
    except ReplayError as exc:
        return None, exc.status


def glyph_registers(state):
    """Translate the oracle result to the public register names in hb-shape."""
    result = []
    for slot, value in state.items():
        if slot in "abcdefghijklmnopqrstuvwx" and len(slot) == 1:
            value = "0" if value == 0 else ("W" if value > 0 else "B")+str(abs(value))
        result.append(f"r_{slot}_{value}")
    return result
