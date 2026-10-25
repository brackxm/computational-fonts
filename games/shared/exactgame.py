# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Compile a finite, exactly solved game into a forward-reading font.

Rules expose INITIAL=(board, player), moves(node), winner(node), and TOKENS.
Players are 0 and 1; winner is None during play, the winning player, or 2 (draw).
An optional choose(node) supplies a score-optimal policy for scoring games.
All solving happens at build time. The resulting font contains transitions,
not Python, and accepts only the human's moves after h (human first) or b.
"""
from collections import defaultdict, deque
import heapq

from fontgame import GameFont, group
from game_text import NAME_RECORDS, centered_lettering

STATUS = {'ready': 1, 'computer_won': 2, 'human_won': 3,
          'invalid': 4, 'malformed': 5, 'internal': 6, 'draw': 7}
LABELS = ('Your turn', 'Font wins', 'You win', 'Invalid move',
          'Check your input', 'Game error', 'Draw')


class Policy:
    def __init__(self, rules):
        self.rules = rules
        pending = [rules.INITIAL]
        self.graph = {}
        while pending:
            node = pending.pop()
            if node in self.graph:
                continue
            self.graph[node] = {} if rules.winner(node) is not None else rules.moves(node)
            pending.extend(child for child in self.graph[node].values() if child not in self.graph)
        self.nodes = tuple(sorted(self.graph))
        self.outcomes, self.distances = self._solve()

    def _solve(self):
        """Retrograde attractors; unresolved cycles are draws. Distance orders wins."""
        parents = defaultdict(list)
        remaining = {node: len(children) for node, children in self.graph.items()}
        for node, options in self.graph.items():
            for child in options.values():
                parents[child].append(node)
        outcomes, distances, longest, pending = {}, {}, defaultdict(int), []
        for node in self.nodes:
            winner = self.rules.winner(node)
            if winner is not None:
                outcomes[node], distances[node] = winner, 0
                if winner != 2:
                    heapq.heappush(pending, (0, node))
        while pending:
            distance, child = heapq.heappop(pending)
            for parent in parents[child]:
                if parent in outcomes:
                    continue
                winner = outcomes[child]
                if winner == parent[1]:
                    outcomes[parent], distances[parent] = winner, distance+1
                    heapq.heappush(pending, (distance+1, parent))
                else:
                    remaining[parent] -= 1
                    longest[parent] = max(longest[parent], distance)
                    if remaining[parent] == 0:
                        outcomes[parent], distances[parent] = winner, longest[parent]+1
                        heapq.heappush(pending, (longest[parent]+1, parent))
        for node in self.nodes:
            if node not in outcomes:
                outcomes[node], distances[node] = 2, None
        return outcomes, distances

    def solve(self, node):
        return self.outcomes[node], self.distances[node]

    def draw_status(self, node, human):
        return 'invalid' if self.solve(node)[0] == 1-human else 'draw'

    def choose(self, node):
        if hasattr(self.rules, 'choose'):
            return self.rules.choose(node)
        winner, distance = self.solve(node)
        return min(token for token, child in self.graph[node].items()
                   if self.solve(child)[0] == winner and
                   (winner == 2 or self.solve(child)[1] == distance - 1))

    def settle(self, node, human):
        """Play the font's turn(s), returning board, last token, and status."""
        last = None
        while self.rules.winner(node) is None and node[1] != human:
            last = self.choose(node)
            node = self.graph[node][last]
        winner = self.rules.winner(node)
        status = ('ready' if winner is None else 'draw' if winner == 2
                  else 'human_won' if winner == human else 'computer_won')
        return node, last, status

    def replay(self, source):
        text = ''.join(c for c in source if c not in ' \t\r\n')
        node, last = self.rules.INITIAL, None
        if not text or text[0] not in 'hb':
            return node, last, 'malformed'
        human = 0 if text[0] == 'h' else 1
        node, last, status = self.settle(node, human)
        text = text[1:]
        while text and status == 'ready':
            if getattr(self.rules, 'DRAW_OFFER', False) and text.startswith('='):
                return node, last, self.draw_status(node, human)
            token, separator, text = text.partition(';')
            token += separator
            if token not in self.rules.TOKENS:
                return node, last, 'malformed'
            if token not in self.graph[node]:
                return node, last, 'invalid'
            node, move, status = self.settle(self.graph[node][token], human)
            if move is not None:
                last = move
        return node, last, status


def build_game(rules, title, output, frame, paint, highlight, *, share_contours=False):
    """Artwork callbacks add reusable components; all cursor art is shared."""
    policy = Policy(rules)
    f = GameFont(title + ' Perfect Opponent', 1800, 1250, name_records=NAME_RECORDS)
    raw = f.raw
    f.add('board', frame, advance=1800, overlay=False)
    ids = {node: i for i, node in enumerate(policy.nodes)}
    paints = {board: paint(f, board) for board in sorted({n[0] for n in policy.nodes})}
    for human in (0, 1):
        text = 'You play first' if human == 0 else 'Font plays first'
        f.add(f'role_{human}', lambda p, s, text=text: centered_lettering(p, text, s+900, 165, 9, weight='regular'))
    if getattr(rules, 'HINTS', False):
        for key, text in (('win', 'You can force a win'), ('loss', 'Font can force a win'), ('draw', 'Draw with perfect play')):
            f.add('hint_'+key, lambda p, s, text=text: centered_lettering(p, text, s+900, 230, 8, weight='regular'))

    def state(name, node, human):
        layers = [*paints[node[0]], (f'role_{human}', 0)]
        if getattr(rules, 'HINTS', False):
            winner = policy.solve(node)[0]
            hint = 'draw' if winner == 2 else 'win' if winner == human else 'loss'
            layers.append(('hint_'+hint, 0))
        return f.layered(name, layers)

    header = state('r_header', rules.INITIAL, 0)
    active, stopped = {}, {}

    def stop(node, human, status):
        key = node, human, status
        if key not in stopped:
            stopped[key] = state(f'r_{status}_h{human}_{ids[node]}', node, human)
        return stopped[key]

    lasts = {token: highlight(f, token) for token in rules.TOKENS}
    last_none = f.add('r_last_none')
    for (status, code), label in zip(STATUS.items(), LABELS):
        if status == 'draw' and 2 not in policy.outcomes.values() and not getattr(rules, 'DRAW_OFFER', False):
            continue
        f.add('status_'+status, lambda p, s, label=label: centered_lettering(p, label, s+900, 30, 11),
              advance=code, color=1 if code < 4 else 2)
    tokens = {token: f.add(f'move_{i}') for i, token in enumerate(rules.TOKENS)}
    inputs = [*raw.values(), *tokens.values()]
    lex = ['sub '+' '.join(raw[c] for c in token)+f' by {name};' for token, name in tokens.items()]
    pending = deque()

    def cursor(node, human, status='ready', last=None):
        if status == 'ready':
            if node not in active:
                active[node] = state(f'r_active_h{human}_{ids[node]}', node, human)
                pending.append(node)
            name = active[node]
        else:
            name = stop(node, human, status)
        return name + (' '+lasts[last] if last is not None else '')

    transitions = []
    for mode, human in (('h', 0), ('b', 1)):
        node, last, status = policy.settle(rules.INITIAL, human)
        transitions.append(f'sub {header} {raw[mode]}\' by {cursor(node, human, status, last)};')
    bad_start = [n for n in inputs if n not in (raw['h'], raw['b'])]
    transitions.append(f'sub {header} {group(bad_start)}\' by {stop(rules.INITIAL, 0, "malformed")};')
    while pending:
        node = pending.popleft()
        human = node[1]
        name, options = active[node], policy.graph[node]
        if getattr(rules, 'DRAW_OFFER', False):
            status = policy.draw_status(node, human)
            transitions.append(f'sub {name} {raw["="]}\' by {stop(node, human, status)};')
        bad = [token for key, token in tokens.items() if key not in options]
        if bad:
            transitions.append(f'sub {name} {group(bad)}\' by {stop(node, human, "invalid")};')
        for token, child in sorted(options.items()):
            child, last, status = policy.settle(child, human)
            transitions.append(f'sub {name} {tokens[token]}\' by {cursor(child, human, status, last)};')
        transitions.append(f'sub {name} {group(raw.values())}\' by {stop(node, human, "malformed")};')
    states = [header, *active.values(), *stopped.values()]
    finish = [f'sub {group(active.values())} end\' by status_ready;',
              f'sub {header} end\' by status_malformed;']
    by_status = defaultdict(list)
    for (_, _, status), name in stopped.items():
        by_status[status].append(name)
    finish += [f'sub {group(names)} end\' by status_{status};' for status, names in by_status.items()]
    program = f.forward_program(['board', header, last_none], states, [last_none, *lasts.values()],
                                list(stopped.values()), transitions, finish, inputs=inputs,
                                preprocess=[('MOVES', lex, list(raw.values()))])
    return f.save(output, program, [], [], 1, compact=True, share_contours=share_contours)
