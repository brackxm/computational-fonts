# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Test-only model of the minimized independent controller; never a UI import."""
from dataclasses import dataclass
import independent as c


@dataclass
class State:
    red: int
    yellow: int
    mode: tuple
    status: str = 'ready'
    last: int = 4


class Reference:
    def __init__(self, controller):
        self.controller = controller
        first = controller['initial_action']
        if first[0] != 'move':
            raise ValueError('expected prescribed first move')
        self.first, self.first_mode = first[1], first[2]

    def mode(self, index):
        tag, *args = self.controller['modes'][index]
        return ('policy', args[0]) if tag == 'policy' else (tag, index)

    def start(self):
        red, yellow = c.place(0, 0, self.first-1, 1)
        return State(red, yellow, self.mode(self.first_mode), last=self.first)

    def human(self, state, char):
        if state.status == 'win':
            state.status = 'trailing'
            return state
        if state.status != 'ready':
            return state
        if char not in '1234567':
            state.status = 'malformed'
            return state
        col = int(char)-1
        if col not in c.legal(state.red, state.yellow):
            state.status = 'full'
            return state
        state.red, state.yellow = c.place(state.red, state.yellow, col, 2)
        if c.four(state.yellow):
            state.status = 'yellow'
            return state
        if state.red | state.yellow == c.FULL:
            state.status = 'draw'
            return state
        tag, index = state.mode
        if tag == 'branch':
            action = self.controller['modes'][index][1][col]
            if action[0] == 'move':
                reply = action[1]-1
                state.mode = self.mode(action[2])
            elif action[0] == 'policy':
                state.mode = ('policy', action[1])
                reply = c.ranked(state.red, state.yellow, self.controller['policies'][action[1]])
            else:
                state.status = 'internal'
                return state
        elif tag == 'policy':
            reply = c.ranked(state.red, state.yellow, self.controller['policies'][index])
        else:
            state.status = 'internal'
            return state
        if reply not in c.legal(state.red, state.yellow):
            state.status = 'internal'
            return state
        state.red, state.yellow = c.place(state.red, state.yellow, reply, 1)
        state.last = reply+1
        if c.four(state.red):
            state.status = 'win'
        elif state.red | state.yellow == c.FULL:
            state.status = 'draw'
        return state

    def replay(self, source):
        state = self.start()
        if not source.startswith('b'):
            state.status = 'malformed'
            return state
        for char in source[1:]:
            self.human(state, char)
        return state


def decode_shape(shaped):
    red = yellow = 0
    last = None
    for name, advance, x, y in shaped:
        if name.startswith('r_c'):
            col, row, who = map(int, name[3:].split('_'))
            if who:
                if who == 1:
                    red |= 1 << (7*col+row)
                else:
                    yellow |= 1 << (7*col+row)
        elif name.startswith('r_last_'):
            last = int(name.removeprefix('r_last_'))
    return red, yellow, last, sum(g[1] for g in shaped)
