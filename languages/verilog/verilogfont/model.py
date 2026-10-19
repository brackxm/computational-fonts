# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Parsed declarations and elaborated, immutable bit drivers."""
from dataclasses import dataclass, field, replace
from .syntax import Expr, SourceLocation


@dataclass(frozen=True)
class Signal:
    name: str
    direction: str
    width: int
    signed: bool = False
    kind: str = 'wire'
    location: SourceLocation | None = None


@dataclass(frozen=True)
class Statement:
    op: str
    args: tuple = ()
    location: SourceLocation | None = None

    def walk(self):
        """Visit statements in source order, including all conditional branches."""
        yield self
        if self.op == 'block':
            bodies = self.args
        elif self.op == 'if':
            bodies = self.args[1:]
        elif self.op == 'case':
            bodies = (*[body for _, body in self.args[1]], self.args[2])
        elif self.op == 'for':
            bodies = self.args[-1:]
        else:
            bodies = ()
        for body in bodies:
            yield from body.walk()


def syntax_children(node):
    """Yield immediate syntax children in source order, including nested tuples."""
    pending = list(reversed(node.args))
    while pending:
        value = pending.pop()
        if isinstance(value, (Expr, Statement)):
            yield value
        elif isinstance(value, tuple):
            pending.extend(reversed(value))


def map_children(node, transform):
    """Rewrite immediate syntax children, including children in nested tuples."""
    def visit(value):
        if isinstance(value, (Expr, Statement)):
            return transform(value)
        if isinstance(value, tuple):
            return tuple(visit(item) for item in value)
        return value
    return replace(node, args=visit(node.args))


@dataclass(frozen=True)
class Instance:
    module: str
    name: str
    parameters: dict
    ports: dict
    location: SourceLocation | None = None


@dataclass
class Definition:
    name: str
    signals: dict
    parameters: dict
    assignments: list
    processes: list
    instances: list
    arrays: dict = field(default_factory=dict)
    genvars: set = field(default_factory=set)
    generates: list = field(default_factory=list)
    functions: dict = field(default_factory=dict)
    locations: dict = field(default_factory=dict)
    location: SourceLocation | None = None


@dataclass
class Module:
    name: str
    signals: dict[str, Signal]
    assignments: dict[str, Expr]
    parameters: dict
    localparams: set[str]
    bit_drivers: dict = field(default_factory=dict)
    checks: list = field(default_factory=list)
    hierarchy: list = field(default_factory=list)
    captures: dict = field(default_factory=dict)

    @property
    def inputs(self):
        return [s for s in self.signals.values() if s.direction == 'input']

    @property
    def outputs(self):
        return [s for s in self.signals.values() if s.direction == 'output']
