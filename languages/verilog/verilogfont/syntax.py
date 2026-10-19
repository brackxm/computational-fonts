# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Shared syntax and finite constant values for Verilog elaboration."""
from dataclasses import dataclass, field, replace
from functools import wraps
from fontcircuit.gsub.circuit import ResourceLimit

MAX_WIDTH = 64
MAX_DEPTH = 64
REDUCTIONS = {'&', '~&', '|', '~|', '^', '~^', '^~'}
COMPARISONS = {'==', '!=', '<', '<=', '>', '>='}


def operator_type(op, types):
    """Verilog width/signedness rules shared by constant and circuit expressions."""
    if op in COMPARISONS or op in ('&&', '||', 'unary!') or (
            op.startswith('unary') and op[5:] in REDUCTIONS):
        return 1, False
    if op in ('signed', 'unsigned'):
        return types[0][0], op == 'signed'
    if op in ('<<', '>>', '<<<', '>>>') or op.startswith('unary'):
        return types[0]
    operands = types[1:] if op == '?:' else types
    return max(width for width, _ in operands), all(signed for _, signed in operands)


@dataclass(frozen=True)
class SourceLocation:
    filename: str
    line: int
    column: int
    text: str


class SourceText(str):
    """A string with file boundaries, including when several files are compiled."""
    def __new__(cls, value, filename='<source>', spans=None):
        obj = super().__new__(cls, value)
        obj.spans = spans or [(0, len(value), filename)]
        obj.line_cache = {}
        return obj

    @classmethod
    def combine(cls, files):
        pieces, spans, offset = [], [], 0
        for filename, source in files:
            if pieces:
                pieces.append('\n')
                offset += 1
            pieces.append(source)
            spans.append((offset, offset+len(source), str(filename)))
            offset += len(source)
        return cls(''.join(pieces), spans=spans)

    def location(self, offset):
        start, end, filename = next((s for s in self.spans if s[0] <= offset <= s[1]), self.spans[-1])
        offset = min(max(start, offset), end)
        line_start = self.rfind('\n', start, offset)+1
        line_start = max(start, line_start)
        key = (start,line_start)
        if key not in self.line_cache:
            line_end = self.find('\n', offset, end)
            self.line_cache[key] = (self.count('\n', start, offset)+1,
                                   self[line_start:end if line_end < 0 else line_end])
        line,text = self.line_cache[key]
        return SourceLocation(filename,line,offset-line_start+1,text)


class VerilogError(ValueError):
    def __init__(self, message, location=None):
        self.message, self.location = str(message), location
        super().__init__(self.message)

    def at(self, location):
        if self.location is None:
            self.location = location
        return self

    def __str__(self):
        if self.location is None:
            return self.message
        loc = self.location
        return f'{loc.filename}:{loc.line}:{loc.column}: {self.message}\n  {loc.text}\n  {" "*(loc.column-1)}^'


class VerilogResourceLimit(VerilogError, ResourceLimit):
    """Keep ResourceLimit compatibility while adding source diagnostics."""


def diagnostic(method):
    """Attach the nearest source expression to parser/elaborator errors."""
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        location = getattr(args[0], 'location', None) if args else None
        if location is None and hasattr(self, 'locations'):
            location = self.locations[min(self.pos, len(self.locations)-1)]
        try:
            result = method(self, *args, **kwargs)
        except VerilogError as error:
            raise error.at(location) from None
        except ResourceLimit as error:
            raise VerilogResourceLimit(f'{error}; reduce expression size or increase --max-gates (maximum 32000)', location) from None
        if hasattr(result, 'location') and result.location is None:
            result = replace(result, location=location)
        return result
    return wrapped


@dataclass(frozen=True)
class Expr:
    op: str
    args: tuple = ()
    location: SourceLocation | None = field(default=None, compare=False)


@dataclass(frozen=True)
class Constant:
    bits: int
    width: int
    signed: bool = False

    @property
    def integer(self):
        if self.signed and self.bits & (1 << (self.width - 1)):
            return self.bits - (1 << self.width)
        return self.bits

    def resized(self, width, signed=None):
        signed = self.signed if signed is None else signed
        value = self.integer if signed and self.signed else self.bits
        return Constant(value & ((1 << width)-1), width, signed)
