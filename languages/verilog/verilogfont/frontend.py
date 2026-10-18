# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Strict frontend for a finite, unsigned, combinational Verilog-2001 subset.

Only continuous assignments are accepted. Unsupported syntax is rejected,
including unused declarations and assignments, rather than silently ignored.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from fontcircuit.gsub.circuit import Circuit, Value


class VerilogError(ValueError):
    pass


MAX_WIDTH = 64
MAX_SIGNALS = 128
MAX_SOURCE = 65536
MAX_TOKENS = 8192
MAX_DEPTH = 64
KEYWORDS = set('module endmodule input output wire assign signed unsigned reg logic '
               'inout parameter localparam always initial begin end generate endgenerate '
               'integer real function endfunction task endtask if else case endcase '
               'for while repeat posedge negedge supply0 supply1 tri wand wor '
               'and automatic buf bufif0 bufif1 cell cmos config '
               'deassign default defparam design disable edge endconfig endprimitive '
               'endspecify endtable event force forever fork genvar highz0 highz1 '
               'ifnone incdir include instance join large liblist library '
               'macromodule medium nand nmos nor noshowcancelled not notif0 notif1 '
               'or pmos primitive pull0 pull1 pulldown pullup pulsestyle_onevent '
               'pulsestyle_ondetect rcmos realtime release rnmos rpmos rtran rtranif0 '
               'rtranif1 scalared showcancelled small specify specparam strong0 '
               'strong1 table time tran tranif0 tranif1 tri0 tri1 triand trior trireg '
               'use vectored wait weak0 weak1 xnor xor'.split())
TOKEN = re.compile(r"\s+|//[^\n]*|/\*[\s\S]*?\*/|"
                   r"[0-9][0-9_]*'[bBoOdDhH][0-9a-fA-F_xXzZ?]+|"
                   r"[0-9][0-9_]*|[a-zA-Z_][a-zA-Z_0-9$]*|"
                   r"===|!==|>>>|<<<|<<|>>|<=|>=|==|!=|&&|\|\||~\^|\^~|~&|~\||"
                   r"[()\[\]{};,:?=+*~!&|^<>-]")
PRECEDENCE = {'||': 1, '&&': 2, '|': 3, '^': 4, '^~': 4, '~^': 4,
              '&': 5, '==': 6, '!=': 6, '<': 7, '<=': 7, '>': 7, '>=': 7,
              '<<': 8, '>>': 8, '+': 9, '-': 9, '*': 10}
REDUCTIONS = {'&', '~&', '|', '~|', '^', '~^', '^~'}
COMPARISONS = {'==', '!=', '<', '<=', '>', '>='}


@dataclass(frozen=True)
class Signal:
    name: str
    direction: str
    width: int


@dataclass(frozen=True)
class Expr:
    op: str
    args: tuple = ()


@dataclass
class Module:
    name: str
    signals: dict[str, Signal]
    assignments: dict[str, Expr]

    @property
    def inputs(self):
        return [s for s in self.signals.values() if s.direction == 'input']

    @property
    def outputs(self):
        return [s for s in self.signals.values() if s.direction == 'output']


class Parser:
    def __init__(self, source):
        if len(source) > MAX_SOURCE:
            raise VerilogError(f'source exceeds {MAX_SOURCE} characters')
        self.tokens = []
        offset = 0
        while offset < len(source):
            match = TOKEN.match(source, offset)
            if not match:
                line = source.count('\n', 0, offset) + 1
                raise VerilogError(f'unsupported character or syntax at line {line}: {source[offset:offset+20]!r}')
            token = match[0]
            if not token.isspace() and not token.startswith(('//', '/*')):
                self.tokens.append(token)
            offset = match.end()
        if len(self.tokens) > MAX_TOKENS:
            raise VerilogError(f'source exceeds {MAX_TOKENS} tokens')
        self.tokens.append('<eof>')
        self.pos = 0
        self.signals = {}

    def peek(self):
        return self.tokens[self.pos]

    def take(self, expected=None):
        token = self.peek()
        if expected is not None and token != expected:
            raise VerilogError(f'expected {expected!r}, found {token!r}')
        if token == '<eof>':
            raise VerilogError('unexpected end of source')
        self.pos += 1
        return token

    def accept(self, token):
        if self.peek() == token:
            self.take()
            return True
        return False

    def identifier(self):
        name = self.take()
        if not re.fullmatch(r'[a-zA-Z_][a-zA-Z_0-9$]*', name) or name in KEYWORDS:
            raise VerilogError(f'expected an identifier, found {name!r}')
        return name

    def integer(self):
        token = self.take()
        if not re.fullmatch(r'[0-9][0-9_]*', token):
            raise VerilogError('indices, ranges and repeat counts require decimal integer literals')
        if len(token) > 16:
            raise VerilogError('integer literal is too large')
        return int(token.replace('_', ''))

    def width(self):
        if not self.accept('['):
            return 1
        high = self.integer()
        self.take(':')
        low = self.integer()
        self.take(']')
        if low != 0 or not 0 <= high < MAX_WIDTH:
            raise VerilogError(f'ranges must be descending [N:0], with width 1–{MAX_WIDTH}')
        return high + 1

    def declare(self, name, direction, width):
        if name in self.signals:
            raise VerilogError(f'duplicate declaration: {name}')
        if len(self.signals) >= MAX_SIGNALS:
            raise VerilogError(f'at most {MAX_SIGNALS} signals are supported')
        self.signals[name] = Signal(name, direction, width)

    def parse(self):
        self.take('module')
        name = self.identifier()
        self.take('(')
        direction, width = None, 1
        if self.peek() != ')':
            while True:
                if self.peek() in ('input', 'output'):
                    direction = self.take()
                    self.accept('wire')
                    width = self.width()
                if direction is None:
                    raise VerilogError('use ANSI ports: module name(input ..., output ...)')
                self.declare(self.identifier(), direction, width)
                if not self.accept(','):
                    break
        self.take(')')
        self.take(';')
        assignments = {}
        while self.peek() != 'endmodule':
            if self.accept('wire'):
                width = self.width()
                while True:
                    self.declare(self.identifier(), 'wire', width)
                    if not self.accept(','):
                        break
                self.take(';')
            elif self.accept('assign'):
                while True:
                    target = self.identifier()
                    self.take('=')
                    if target in assignments:
                        raise VerilogError(f'multiple drivers for {target}')
                    assignments[target] = self.expr()
                    if not self.accept(','):
                        break
                self.take(';')
            else:
                raise VerilogError(f'unsupported module item {self.peek()!r}; use wire and assign')
        self.take('endmodule')
        if self.peek() != '<eof>':
            raise VerilogError('exactly one module is supported')
        if not any(s.direction == 'output' for s in self.signals.values()):
            raise VerilogError('at least one output port is required')
        for target in assignments:
            if target not in self.signals:
                raise VerilogError(f'undeclared assignment target: {target}')
            if self.signals[target].direction == 'input':
                raise VerilogError(f'cannot drive input: {target}')
        for signal in self.signals.values():
            if signal.direction != 'input' and signal.name not in assignments:
                raise VerilogError(f'undriven signal: {signal.name}')
        return Module(name, self.signals, assignments)

    def expr(self, minimum=0, depth=0):
        if depth >= MAX_DEPTH:
            raise VerilogError(f'expression nesting exceeds {MAX_DEPTH}')
        token = self.take()
        if token in ('~', '!', '+', '-') or token in REDUCTIONS:
            left = Expr('unary' + token, (self.expr(11, depth+1),))
        elif token == '(':
            left = self.expr(depth=depth+1)
            self.take(')')
        elif token == '{':
            # A replication starts with an unsized decimal count and another {.
            if (re.fullmatch(r'[0-9][0-9_]*', self.peek()) and
                    self.tokens[self.pos+1] == '{'):
                count = self.integer()
                if not 1 <= count <= MAX_WIDTH:
                    raise VerilogError(f'repeat count must be 1–{MAX_WIDTH}')
                self.take('{')
                items = [self.expr(depth=depth+1)]
                while self.accept(','):
                    items.append(self.expr(depth=depth+1))
                self.take('}')
                self.take('}')
                left = Expr('repeat', (count, Expr('concat', tuple(items))))
            else:
                items = [self.expr(depth=depth+1)]
                while self.accept(','):
                    items.append(self.expr(depth=depth+1))
                self.take('}')
                left = Expr('concat', tuple(items))
        elif re.fullmatch(r"[0-9][0-9_]*'[bBoOdDhH][0-9a-fA-F_xXzZ?]+", token):
            size, digits = token.split("'")
            if len(size) > 16:
                raise VerilogError('literal width is too large')
            width = int(size.replace('_', ''))
            if not 1 <= width <= MAX_WIDTH:
                raise VerilogError(f'literal width must be 1–{MAX_WIDTH}')
            if any(c in digits.lower() for c in 'xz?'):
                raise VerilogError('X/Z/? literals are unsupported; this is a two-state compiler')
            if len(digits) > 256:
                raise VerilogError('literal is too long')
            radix, pattern = {
                'b': (2, r'[01][01_]*'),
                'o': (8, r'[0-7][0-7_]*'),
                'd': (10, r'[0-9][0-9_]*'),
                'h': (16, r'[0-9a-fA-F][0-9a-fA-F_]*'),
            }[digits[0].lower()]
            # Validate Verilog digits before normalization: Python's int()
            # accepts a 0b prefix, and removing underscores hides a leading _.
            if not re.fullmatch(pattern, digits[1:]):
                raise VerilogError(f'invalid based literal: {token}')
            value = int(digits[1:].replace('_', ''), radix)
            left = Expr('literal', (value & ((1 << width)-1), width))
        elif re.fullmatch(r'[0-9][0-9_]*', token):
            raise VerilogError(f'use an unsigned sized literal in expressions, e.g. 8\'d{token}')
        elif re.fullmatch(r'[a-zA-Z_][a-zA-Z_0-9$]*', token) and token not in KEYWORDS:
            left = Expr('name', (token,))
            if self.accept('['):
                high = self.integer()
                low = self.integer() if self.accept(':') else high
                self.take(']')
                left = Expr('select', (left, high, low))
        else:
            raise VerilogError(f'unsupported expression token: {token!r}')
        while self.peek() in PRECEDENCE and PRECEDENCE[self.peek()] >= minimum:
            op = self.take()
            right = self.expr(PRECEDENCE[op]+1, depth+1)
            left = Expr(op, (left, right))
        if minimum == 0 and self.accept('?'):
            yes = self.expr(depth=depth+1)
            self.take(':')
            no = self.expr(depth=depth+1)
            left = Expr('?:', (left, yes, no))
        return left


def resize(value, width):
    return Value((value.bits + (0,)*max(0, width-value.width))[:width])


class Lowerer:
    def __init__(self, module, max_gates=12000):
        self.module = module
        self.circuit = Circuit(max_gates=max_gates)
        self.values = {signal.name: self.circuit.argument(i, signal.width)
                       for i, signal in enumerate(module.inputs)}
        self.visiting = set()
        self.widths = {}

    def width(self, expr, depth=0):
        if depth >= MAX_DEPTH:
            raise VerilogError(f'expression tree depth exceeds {MAX_DEPTH}')
        if id(expr) in self.widths:
            return self.widths[id(expr)]
        op, args = expr.op, expr.args
        if op == 'literal':
            width = args[1]
        elif op == 'name':
            if args[0] not in self.module.signals:
                raise VerilogError(f'undeclared signal: {args[0]}')
            width = self.module.signals[args[0]].width
        elif op == 'select':
            base, high, low = args
            if not 0 <= low <= high < self.width(base, depth+1):
                raise VerilogError('bit/part select is outside its signal range')
            width = high-low+1
        elif op == 'concat':
            width = sum(self.width(a, depth+1) for a in args)
        elif op == 'repeat':
            width = args[0]*self.width(args[1], depth+1)
        else:
            sizes = [self.width(a, depth+1) for a in args]
            is_reduction = op.startswith('unary') and op[5:] in REDUCTIONS
            if op in COMPARISONS or op in ('&&', '||', 'unary!') or is_reduction:
                width = 1
            elif op in ('<<', '>>') or op.startswith('unary'):
                width = sizes[0]
            elif op == '?:':
                width = max(sizes[1:])
            else:
                width = max(sizes)
        if not 1 <= width <= MAX_WIDTH:
            raise VerilogError(f'expression width exceeds {MAX_WIDTH} bits')
        self.widths[id(expr)] = width
        return width

    def signal(self, name):
        if name in self.values:
            return self.values[name]
        if name in self.visiting:
            raise VerilogError(f'combinational cycle involving {name}')
        self.visiting.add(name)
        signal = self.module.signals[name]
        value = resize(self.lower(self.module.assignments[name], signal.width), signal.width)
        self.values[name] = value
        self.visiting.remove(name)
        return value

    def lower(self, expr, context=0):
        c = self.circuit
        op, args = expr.op, expr.args
        natural = self.width(expr)
        width = max(natural, context)
        if op == 'literal':
            return c.const(args[0], width)
        if op == 'name':
            return resize(self.signal(args[0]), width)
        if op == 'select':
            value = self.lower(args[0])
            return resize(Value(value.bits[args[2]:args[1]+1]), width)
        if op == 'concat':
            return resize(Value(tuple(bit for a in reversed(args) for bit in self.lower(a).bits)), width)
        if op == 'repeat':
            return resize(Value(self.lower(args[1]).bits * args[0]), width)
        if op == '?:':
            return c.mux(c.nonzero(self.lower(args[0])), self.lower(args[1], width), self.lower(args[2], width))
        if op.startswith('unary'):
            operator = op[5:]
            a = self.lower(args[0], 0 if operator in REDUCTIONS or operator == '!' else width)
            if operator == '+': return a
            if operator == '-': return c.add(c.const(0, width), a, True)
            if operator == '~': return Value(tuple(c.NOT(bit) for bit in a.bits))
            if operator == '!': return resize(Value((c.NOT(c.nonzero(a)),)), width)
            value = 1 if operator in ('&', '~&') else 0
            fn = c.AND if operator in ('&', '~&') else c.OR if operator in ('|', '~|') else c.XOR
            for bit in a.bits:
                value = fn(value, bit)
            if operator in ('~&', '~|', '~^', '^~'):
                value = c.NOT(value)
            return resize(Value((value,)), width)
        if op in ('&&', '||'):
            a, b = (c.nonzero(self.lower(a)) for a in args)
            return resize(Value(((c.AND if op == '&&' else c.OR)(a, b),)), width)
        if op in COMPARISONS:
            operand_width = max(self.width(a) for a in args)
            a, b = (self.lower(a, operand_width) for a in args)
            if op in ('==', '!='):
                value = c.eq(a, b)
            else:
                value = c.lt(b, a) if op in ('>', '<=') else c.lt(a, b)
            if op in ('!=', '<=', '>='): value = c.NOT(value)
            return resize(Value((value,)), width)
        if op in ('<<', '>>'):
            a, amount = self.lower(args[0], width), self.lower(args[1])
            bits = a.bits
            # Verilog shifts do not mask the count to log2(width), unlike Wasm.
            for level, bit in enumerate(amount.bits):
                distance = 1 << level
                if distance >= width: other = (0,)*width
                elif op == '<<': other = (0,)*distance + bits[:-distance]
                else: other = bits[distance:] + (0,)*distance
                bits = tuple(c.MUX(bit, new, old) for new, old in zip(other, bits))
            return Value(bits)
        a, b = (self.lower(a, width) for a in args)
        if op in ('+', '-'): return c.add(a, b, op == '-')
        if op == '*': return c.mul(a, b)
        value = c.bitwise({'&': 'and', '|': 'or', '^': 'xor', '~^': 'xor', '^~': 'xor'}[op], a, b)
        return Value(tuple(c.NOT(bit) for bit in value.bits)) if op in ('~^', '^~') else value

    def compile(self):
        # Validate and lower every driver, including unused wires, to detect
        # unsupported expressions, undeclared names and hidden cycles.
        for expr in self.module.assignments.values():
            self.width(expr)
        for name in self.module.assignments:
            self.signal(name)
        return self.circuit, [self.values[s.name] for s in self.module.outputs]


def compile_source(source, *, max_gates=12000):
    try:
        module = Parser(source).parse()
        circuit, results = Lowerer(module, max_gates).compile()
    except RecursionError:
        raise VerilogError('source exceeds compiler nesting capacity') from None
    return module, circuit, results
