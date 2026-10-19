# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Strict frontend for a finite, two-state, combinational Verilog-2005 subset.

Combinational blocks and module instances elaborate to bit drivers. Unsupported syntax is rejected,
including unused declarations and assignments, rather than silently ignored.
"""
from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
import re

from fontcircuit.gsub.circuit import Circuit, Value
from .syntax import (Expr, VerilogError, VerilogResourceLimit, SourceText, diagnostic,
                     operator_type, REDUCTIONS, COMPARISONS, MAX_WIDTH, MAX_DEPTH)
from .constants import ConstantEvaluator, ParameterDecl
from .model import Signal, Module, Definition, Instance, Statement
from .arithmetic import Division

MAX_SIGNALS = 128
MAX_PARAMETERS = 128
MAX_SOURCE = 65536
MAX_TOKENS = 8192
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
                   r"[0-9][0-9_]*'[sS]?[bBoOdDhH][0-9a-fA-F_xXzZ?]+|"
                   r"[0-9][0-9_]*|\$(?:clog2|signed|unsigned)|[a-zA-Z_][a-zA-Z_0-9$]*|"
                   r"===|!==|>>>|<<<|<<|>>|<=|>=|==|!=|&&|\|\||~\^|\^~|~&|~\||"
                   r"\+:|-:|[()\[\]{};,:?=+*/%~!&|^<>#@.-]")
PRECEDENCE = {'||': 1, '&&': 2, '|': 3, '^': 4, '^~': 4, '~^': 4,
              '&': 5, '==': 6, '!=': 6, '<': 7, '<=': 7, '>': 7, '>=': 7,
              '<<': 8, '>>': 8, '<<<': 8, '>>>': 8, '+': 9, '-': 9, '*': 10, '/': 10, '%': 10}


class Parser:
    def __init__(self, source, *, parameters=None, top=None, source_name="<source>"):
        source = source if isinstance(source, SourceText) else SourceText(source, source_name)
        self.locations = []
        self.pos = 0
        if len(source) > MAX_SOURCE:
            raise VerilogResourceLimit(f'source exceeds {MAX_SOURCE} characters; split or reduce the design', source.location(0))
        self.top = top
        self.tokens = []
        offset = 0
        while offset < len(source):
            match = TOKEN.match(source, offset)
            if not match:
                line = source.count('\n', 0, offset) + 1
                raise VerilogError(f'unsupported character or syntax at line {line}: {source[offset:offset+20]!r}', source.location(offset))
            token = match[0]
            if not token.isspace() and not token.startswith(('//', '/*')):
                self.tokens.append(token)
                self.locations.append(source.location(offset))
            offset = match.end()
        if len(self.tokens) > MAX_TOKENS:
            raise VerilogResourceLimit(f'source exceeds {MAX_TOKENS} tokens; reduce the design', source.location(offset))
        self.tokens.append('<eof>')
        self.locations.append(source.location(len(source)))
        self.pos = 0
        self.new_namespace()
        self.generate_number = 0
        self.overrides = {}
        if parameters is not None and not isinstance(parameters, Mapping):
            raise VerilogError('parameter overrides must be a mapping of names to values')
        for name, value in (parameters or {}).items():
            if not isinstance(name, str) or not re.fullmatch(r'[a-zA-Z_][a-zA-Z_0-9$]*', name):
                raise VerilogError('parameter override names must be identifiers')
            if type(value) is int:
                value = str(value)
            if not isinstance(value, str) or not re.fullmatch(
                    r"[+-]?(?:[0-9][0-9_]*|[0-9][0-9_]*'[sS]?[bBoOdDhH][0-9a-fA-F_]+)", value.strip()):
                raise VerilogError(f'override {name} must be a decimal integer or sized literal')
            parser = Parser(value.strip())
            expression = parser.expr()
            if parser.peek() != '<eof>':
                raise VerilogError(f'invalid parameter override: {name}')
            self.overrides[name] = expression

    def peek(self):
        return self.tokens[self.pos]

    @diagnostic
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

    @diagnostic
    def identifier(self):
        name = self.take()
        if not re.fullmatch(r'[a-zA-Z_][a-zA-Z_0-9$]*', name) or name in KEYWORDS:
            raise VerilogError(f'expected an identifier, found {name!r}')
        return name

    def bounds(self):
        if not self.accept('['):
            return None
        high = self.expr()
        self.take(':')
        low = self.expr()
        self.take(']')
        return high, low

    @property
    def declaration_names(self):
        return self.signals.keys() | self.parameter_declarations.keys() | self.genvars | self.functions.keys()

    def check_declaration(self, name):
        if name in self.declaration_names:
            raise VerilogError(f'duplicate declaration: {name}')

    def declare(self, name, direction, bounds, signed=False, kind='wire'):
        self.check_declaration(name)
        if len(self.signals) >= MAX_SIGNALS:
            raise VerilogResourceLimit(f'at most {MAX_SIGNALS} signals are supported')
        self.signals[name] = (direction, bounds, signed, kind)
        self.declaration_locations[name] = self.locations[self.pos-1]

    def parameter(self, bounds, local=False, signed=False):
        name = self.identifier()
        self.check_declaration(name)
        if len(self.parameter_declarations) >= MAX_PARAMETERS:
            raise VerilogResourceLimit(f'at most {MAX_PARAMETERS} parameters are supported')
        self.parameter_positions[name] = self.pos-1
        self.take('=')
        expression = self.expr()
        self.parameter_declarations[name] = ParameterDecl(name, expression, bounds, local, signed)

    def named_arguments(self, *, empty=False):
        self.take('(')
        arguments = {}
        if self.peek() != ')':
            while True:
                self.take('.')
                name = self.identifier()
                if name in arguments:
                    raise VerilogError(f'duplicate named connection: {name}')
                self.take('(')
                arguments[name] = None if empty and self.peek() == ')' else self.expr()
                self.take(')')
                if not self.accept(','):
                    break
        self.take(')')
        return arguments

    def select(self, base):
        while self.accept('['):
            high = self.expr()
            if self.peek() in ('+:', '-:'):
                direction = self.take()
                width = self.expr()
                base = Expr('indexed', (base, high, width, direction), base.location)
            else:
                low = self.expr() if self.accept(':') else high
                base = Expr('select', (base, high, low), base.location)
            self.take(']')
        return base

    def for_header(self):
        self.take('(')
        iterator = self.identifier()
        self.take('=')
        initial = self.expr()
        self.take(';')
        condition = self.expr()
        self.take(';')
        if self.identifier() != iterator:
            raise VerilogError('for loop must update its own iterator')
        self.take('=')
        step = self.expr()
        self.take(')')
        return iterator, initial, condition, step

    @diagnostic
    def target(self, depth=0):
        if depth >= MAX_DEPTH:
            raise VerilogResourceLimit('assignment target nesting exceeds compiler bounds')
        if self.accept('{'):
            items = [self.target(depth+1)]
            while self.accept(','):
                items.append(self.target(depth+1))
            self.take('}')
            return Expr('concat', tuple(items))
        return self.select(Expr('name', (self.identifier(),)))

    @diagnostic
    def statement(self, depth=0):
        if depth >= MAX_DEPTH:
            raise VerilogResourceLimit('statement nesting exceeds compiler bounds')
        if self.accept(';'):
            return Statement('block')
        if self.accept('for'):
            header = self.for_header()
            return Statement('for', (*header, self.statement(depth+1)))
        if self.accept('begin'):
            if self.accept(':'):
                self.identifier()
            items = []
            while self.peek() != 'end':
                items.append(self.statement(depth+1))
            self.take('end')
            return Statement('block', tuple(items))
        if self.accept('if'):
            self.take('(')
            condition = self.expr()
            self.take(')')
            yes = self.statement(depth+1)
            no = self.statement(depth+1) if self.accept('else') else Statement('block')
            return Statement('if', (condition, yes, no))
        if self.accept('case'):
            self.take('(')
            selector = self.expr()
            self.take(')')
            items, default = [], None
            while not self.accept('endcase'):
                if self.accept('default'):
                    if default is not None:
                        raise VerilogError('duplicate case default')
                    self.accept(':')
                    default = self.statement(depth+1)
                else:
                    labels = [self.expr()]
                    while self.accept(','):
                        labels.append(self.expr())
                    self.take(':')
                    items.append((tuple(labels), self.statement(depth+1)))
            return Statement('case', (selector, tuple(items), default or Statement('block')))
        target = self.target()
        if self.peek() == '<=':
            raise VerilogError('nonblocking assignments are unsupported; use blocking = in always @*')
        self.take('=')
        value = self.expr()
        self.take(';')
        return Statement('assign', (target, value), target.location)

    def new_namespace(self):
        self.signals, self.parameter_declarations = {}, {}
        self.parameter_positions, self.references = {}, []
        self.arrays, self.genvars, self.generates, self.functions, self.declaration_locations = {}, set(), [], {}, {}
        self.instance_names = set()

    def namespace(self):
        return {key: getattr(self,key) for key in (
            'signals','parameter_declarations','parameter_positions','references','arrays','genvars',
            'generates','functions','declaration_locations','instance_names')}

    def finish_definition(self, name, assignments, processes, instances, location=None):
        if self.instance_names & self.declaration_names:
            raise VerilogError('instance name collides with a declaration')
        for reference, position in self.references:
            if reference in self.parameter_positions and position < self.parameter_positions[reference]:
                raise VerilogError(f'parameter referenced before declaration: {reference}', self.locations[position])
        return Definition(name, self.signals, self.parameter_declarations,
                          assignments, processes, instances, self.arrays, self.genvars,
                          self.generates, self.functions, self.declaration_locations, location)

    def declaration_type(self, integer=False):
        if integer:
            return True, (Expr('literal', (31,32)), Expr('literal', (0,32)))
        return self.accept('signed'), self.bounds()

    def declaration(self, assignments):
        kind = self.take()
        signed, bounds = self.declaration_type(kind == 'integer')
        while True:
            name = self.identifier()
            self.declare(name, kind, bounds, signed, 'reg' if kind == 'input' else kind)
            if self.peek() == '[':
                if kind == 'input':
                    raise VerilogError('array function inputs are unsupported; pass individual words')
                self.arrays[name] = self.bounds()
            if self.accept('='):
                if kind != 'wire':
                    raise VerilogError('reg initializers imply state; assign inside always @*')
                assignments.append((Expr('name',(name,),self.declaration_locations[name]), self.expr()))
            if not self.accept(','): break
        self.take(';')

    def function(self):
        location = self.locations[self.pos]
        self.take('function')
        self.accept('automatic')
        signed, bounds = self.declaration_type(self.accept('integer'))
        name = self.identifier()
        self.check_declaration(name)
        outer = self.namespace()
        self.new_namespace()
        self.declare(name, 'output', bounds, signed, 'reg')
        if self.accept('('):
            if self.peek() != ')':
                first, input_bounds, input_signed = True, None, False
                while True:
                    if self.accept('input'):
                        self.accept('reg')
                        input_signed, input_bounds = self.declaration_type(self.accept('integer'))
                        first = False
                    elif first:
                        raise VerilogError('function arguments must be input declarations')
                    self.declare(self.identifier(), 'input', input_bounds, input_signed, 'reg')
                    if not self.accept(','): break
            self.take(')')
        self.take(';')
        while self.peek() in ('input','reg','integer'):
            self.declaration([])
        if not any(decl[0] == 'input' for decl in self.signals.values()):
            raise VerilogError('Verilog-2005 functions require at least one input')
        body = self.statement()
        self.take('endfunction')
        definition = self.finish_definition(name, [], [body], [], location)
        for key,value in outer.items(): setattr(self,key,value)
        self.functions[name] = definition

    def generate_body(self):
        location = self.locations[self.pos]
        label = None
        outer = self.namespace()
        self.new_namespace()
        if self.accept('begin'):
            if self.accept(':'): label = self.identifier()
            assignments, processes, instances = self.items('end')
            self.take('end')
        else:
            assignments, processes, instances = self.items(None)
        definition = self.finish_definition(label or '', assignments, processes, instances, location)
        for key,value in outer.items(): setattr(self,key,value)
        if label is None:
            self.generate_number += 1
            label = f'genblk{self.generate_number}'
        return label, definition

    def items(self, until):
        assignments, processes, instances = [], [], []
        while until is None or self.peek() != until:
            location = self.locations[self.pos]
            if self.peek() in ('wire', 'reg', 'integer'):
                self.declaration(assignments)
            elif self.accept('genvar'):
                while True:
                    name = self.identifier()
                    self.check_declaration(name)
                    self.genvars.add(name)
                    if not self.accept(','): break
                self.take(';')
            elif self.peek() == 'function':
                self.function()
            elif self.accept('generate'):
                a,p,i = self.items('endgenerate')
                self.take('endgenerate')
                assignments.extend(a); processes.extend(p); instances.extend(i)
            elif self.accept('for'):
                header = self.for_header()
                label,definition = self.generate_body()
                self.generates.append(Statement('genfor',(*header,label,definition),location))
            elif self.accept('if'):
                self.take('('); condition = self.expr(); self.take(')')
                yes_label,yes = self.generate_body()
                no_label,no = self.generate_body() if self.accept('else') else (None,None)
                self.generates.append(Statement('genif',(condition,yes_label,yes,no_label,no),location))
            elif self.peek() == 'begin':
                label,definition = self.generate_body()
                self.generates.append(Statement('genblock',(label,definition),location))
            elif self.peek() in ('parameter','localparam'):
                local = self.take() == 'localparam'
                signed, bounds = self.declaration_type()
                while True:
                    self.parameter(bounds,local,signed)
                    if not self.accept(','): break
                self.take(';')
            elif self.accept('assign'):
                while True:
                    target = self.target(); self.take('=')
                    assignments.append((target,self.expr()))
                    if not self.accept(','): break
                self.take(';')
            elif self.accept('always'):
                self.take('@')
                if self.accept('('):
                    self.take('*'); self.take(')')
                else: self.take('*')
                processes.append(self.statement())
            else:
                module = self.identifier()
                parameters = self.named_arguments() if self.accept('#') else {}
                while True:
                    instance = self.identifier()
                    if instance in self.instance_names:
                        raise VerilogError(f'duplicate instance: {instance}')
                    self.instance_names.add(instance)
                    instances.append(Instance(module,instance,parameters,self.named_arguments(empty=True),location))
                    if not self.accept(','): break
                self.take(';')
            if until is None: break
        return assignments, processes, instances

    @diagnostic
    def definition(self):
        self.new_namespace()
        location = self.locations[self.pos]
        self.take('module')
        name = self.identifier()
        if self.accept('#'):
            self.take('(')
            self.take('parameter')
            signed, bounds = self.declaration_type()
            while True:
                self.parameter(bounds, signed=signed)
                if not self.accept(','):
                    break
                if self.accept('parameter'):
                    signed, bounds = self.declaration_type()
            self.take(')')
        self.take('(')
        direction, bounds, signed, kind = None, None, False, 'wire'
        if self.peek() != ')':
            while True:
                if self.peek() in ('input', 'output'):
                    direction = self.take()
                    kind = self.take() if self.peek() in ('wire', 'reg') else 'wire'
                    if direction == 'input' and kind == 'reg':
                        raise VerilogError('input reg is not supported in Verilog-2005')
                    signed, bounds = self.declaration_type()
                if direction is None:
                    raise VerilogError('use ANSI ports: module name(input ..., output ...)')
                self.declare(self.identifier(), direction, bounds, signed, kind)
                if not self.accept(','):
                    break
        self.take(')')
        self.take(';')
        self.generate_number = 0
        assignments, processes, instances = self.items('endmodule')
        self.take('endmodule')
        return self.finish_definition(name, assignments, processes, instances, location)

    def parse(self):
        from .elaboration import Elaborator
        definitions = {}
        while self.peek() != '<eof>':
            definition = self.definition()
            if definition.name in definitions:
                raise VerilogError(f'duplicate module: {definition.name}')
            definitions[definition.name] = definition
            if len(definitions) > 32:
                raise VerilogResourceLimit('at most 32 module definitions are supported')
        return Elaborator(definitions, self.overrides, self.top).elaborate()

    @diagnostic
    def expr(self, minimum=0, depth=0):
        if depth >= MAX_DEPTH:
            raise VerilogResourceLimit(f'expression nesting exceeds {MAX_DEPTH}')
        token = self.take()
        if token in ('~', '!', '+', '-') or token in REDUCTIONS:
            left = Expr('unary' + token, (self.expr(11, depth+1),))
        elif token == '(':
            left = self.expr(depth=depth+1)
            self.take(')')
        elif token == '{':
            first = self.expr(depth=depth+1)
            if self.accept('{'):
                items = [self.expr(depth=depth+1)]
                while self.accept(','):
                    items.append(self.expr(depth=depth+1))
                self.take('}')
                self.take('}')
                left = Expr('repeat', (first, Expr('concat', tuple(items))))
            else:
                items = [first]
                while self.accept(','):
                    items.append(self.expr(depth=depth+1))
                self.take('}')
                left = Expr('concat', tuple(items))
        elif re.fullmatch(r"[0-9][0-9_]*'[sS]?[bBoOdDhH][0-9a-fA-F_xXzZ?]+", token):
            size, digits = token.split("'")
            signed = digits[0].lower() == 's'
            if signed:
                digits = digits[1:]
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
            left = Expr('signed_literal' if signed else 'literal', (value & ((1 << width)-1), width))
        elif re.fullmatch(r'[0-9][0-9_]*', token):
            if len(token) > 16 or int(token.replace('_', '')) > 0x7fffffff:
                raise VerilogError('unsized decimal constants must fit a signed 32-bit integer')
            left = Expr('unsized', (int(token.replace('_', '')), 32))
        elif token in ('$clog2', '$signed', '$unsigned'):
            self.take('(')
            left = Expr(token[1:], (self.expr(depth=depth+1),))
            self.take(')')
        elif re.fullmatch(r'[a-zA-Z_][a-zA-Z_0-9$]*', token) and token not in KEYWORDS:
            left = Expr('name', (token,), self.locations[self.pos-1])
            self.references.append((token, self.pos-1))
            if self.accept('('):
                arguments = []
                if self.peek() != ')':
                    arguments.append(self.expr(depth=depth+1))
                    while self.accept(','): arguments.append(self.expr(depth=depth+1))
                self.take(')')
                left = Expr('call',(token,*arguments),left.location)
            left = self.select(left)
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


def resize(value, width, signed=False):
    fill = value.bits[-1] if signed else 0
    return Value((value.bits + (fill,)*max(0, width-value.width))[:width])


class ExpressionTypes:
    def __init__(self, module):
        self.module = module
        self.types = {}

    @diagnostic
    def type_of(self, expr, depth=0):
        if depth >= MAX_DEPTH:
            raise VerilogResourceLimit(f'expression tree depth exceeds {MAX_DEPTH}')
        if id(expr) in self.types:
            return self.types[id(expr)][1]
        op, args = expr.op, expr.args
        if op in ('literal', 'signed_literal', 'unsized'):
            result = (args[1], op != 'literal')
        elif op == 'clog2':
            raise VerilogError('$clog2 is supported only in constant expressions')
        elif op == 'name':
            value = self.module.parameters.get(args[0]) or self.module.signals.get(args[0])
            if value is None:
                raise VerilogError(f'undeclared signal: {args[0]}')
            result = (value.width, value.signed)
        elif op == 'captured':
            result = (args[1], args[2])
        elif op == 'array_read':
            for word in args[0]: self.type_of(word, depth+1)
            self.type_of(args[1], depth+1)
            result = (args[2], args[3])
        elif op == 'typed':
            self.type_of(args[0], depth+1)
            result = (args[1], args[2])
        elif op == 'case_eq':
            for arg in args[:-1]: self.type_of(arg, depth+1)
            result = (1, False)
        elif op == 'index_eq':
            self.type_of(args[0], depth+1)
            result = (1, False)
        elif op in ('bit_select', 'indexed_select'):
            self.type_of(args[0], depth+1)
            self.type_of(args[1], depth+1)
            result = (1 if op == 'bit_select' else args[2], False)
        elif op == 'select':
            base, high, low = args
            if not 0 <= low <= high < self.type_of(base, depth+1)[0]:
                raise VerilogError('bit/part select is outside its signal range')
            result = (high-low+1, False)
        elif op == 'concat':
            if any(ConstantEvaluator.contains_unsized(a) for a in args):
                raise VerilogError('unsized literals are unsupported in concatenations')
            result = (sum(self.type_of(a, depth+1)[0] for a in args), False)
        elif op == 'repeat':
            result = (args[0]*self.type_of(args[1], depth+1)[0], False)
        else:
            types = [self.type_of(a, depth+1) for a in args]
            result = operator_type(op, types)
        if not 1 <= result[0] <= MAX_WIDTH:
            raise VerilogError(f'expression width exceeds {MAX_WIDTH} bits')
        self.types[id(expr)] = (expr,result)  # Retain the source so its ID cannot be reused.
        return result

    def width(self, expr):
        return self.type_of(expr)[0]


class Lowerer(ExpressionTypes):
    def __init__(self, module, max_gates=12000):
        super().__init__(module)
        self.circuit = Circuit(max_gates=max_gates)
        self.values = {signal.name: self.circuit.argument(i, signal.width)
                       for i, signal in enumerate(module.inputs)}
        self.visiting = set()
        self.bit_values = {}
        self.lowered = {}
        self.selected_bits = {}
        self.guard = 1
        self.flags = {}
        self.capture_values = {}
        self.division = Division(self.circuit)

    def merge_flags(self, flags, guard=1):
        for name, value in flags.items():
            self.flags[name] = self.circuit.OR(self.flags.get(name,0), self.circuit.AND(guard,value))

    def flag(self, name, value):
        self.merge_flags({name:value},self.guard)

    def cached(self, cache, key, compute):
        if key not in cache:
            outer = self.flags
            self.flags = {}
            try:
                value = compute()
                cache[key] = (value,self.flags)
            finally:
                self.flags = outer
        value,flags = cache[key]
        self.merge_flags(flags)
        return value

    @contextmanager
    def independent_driver(self, cache, key, cycle_error):
        """Isolate faults without keeping a callback frame on the dependency stack."""
        visiting = (id(cache),key)
        if visiting in self.visiting:
            raise VerilogError(cycle_error)
        self.visiting.add(visiting)
        previous,outer = self.guard,self.flags
        self.guard,self.flags = 1,{}
        try:
            yield
        finally:
            self.guard,self.flags = previous,outer
            self.visiting.remove(visiting)

    def capture(self, identifier):
        if identifier not in self.capture_values:
            with self.independent_driver(self.capture_values,identifier,
                    'combinational cycle through function or procedural value'):
                self.capture_values[identifier] = (self.lower(self.module.captures[identifier]),self.flags)
        value,flags = self.capture_values[identifier]
        self.merge_flags(flags,self.guard)
        return value

    def signal_bit(self, name, index):
        if self.module.signals[name].direction == 'input':
            return self.values[name].bits[index]
        key = (name,index)
        if key not in self.bit_values:
            with self.independent_driver(self.bit_values,key,f'combinational cycle involving {name}[{index}]'):
                self.bit_values[key] = (self.lower(self.module.bit_drivers[name][index]).bits[0],self.flags)
        value,flags = self.bit_values[key]
        self.merge_flags(flags,self.guard)
        return value

    def signal(self, name):
        if self.module.signals[name].direction == 'input': return self.values[name]
        value = Value(tuple(self.signal_bit(name,i) for i in range(self.module.signals[name].width)))
        self.values[name] = value
        return value

    def guarded(self, expression, guard, context=0, signed_context=None):
        previous = self.guard
        self.guard = self.circuit.AND(previous,guard)
        try:
            return self.lower(expression,context,signed_context)
        finally:
            self.guard = previous

    def index_match(self, index, signed, integer):
        low = -(1 << (index.width-1)) if signed else 0
        high = (1 << (index.width-int(signed)))-1
        return self.circuit.eq(index,self.circuit.const(integer,index.width)) if low <= integer <= high else 0

    @diagnostic
    def expression_bit(self, expr, index, context=0, signed_context=None):
        key = (id(expr),index,context,signed_context,self.guard)
        return self.cached(self.selected_bits,key,lambda: self._expression_bit(expr,index,context,signed_context))

    def _expression_bit(self, expr, index, context, signed_context):
        """Resolve structural wiring lazily, without reading unrelated net bits."""
        natural,signed = self.type_of(expr)
        signed = signed if signed_context is None else signed_context
        width = max(natural,context)
        op,args = expr.op,expr.args
        if op == 'name':
            if args[0] in self.module.parameters:
                return self.lower(expr,context,signed_context).bits[index]
            signal = self.module.signals[args[0]]
            if index >= natural:
                if not signed or not signal.signed: return 0
                index = natural-1
            return self.signal_bit(args[0],index)
        if op == 'typed':
            if index >= natural:
                if not signed or not args[2]: return 0
                index = natural-1
            return self.expression_bit(args[0],index,natural)
        if op == 'select':
            return 0 if index >= natural else self.expression_bit(args[0],args[2]+index)
        if op == 'concat':
            for arg in reversed(args):
                size = self.width(arg)
                if index < size: return self.expression_bit(arg,index)
                index -= size
            return 0
        if op == 'repeat':
            return 0 if index >= natural else self.expression_bit(args[1],index % self.width(args[1]))
        if op in ('signed','unsigned'):
            if index >= natural:
                if not signed or op != 'signed': return 0
                index = natural-1
            return self.expression_bit(args[0],index)
        if op == '?:':
            condition = self.circuit.nonzero(self.lower(args[0]))
            previous = self.guard
            try:
                self.guard = self.circuit.AND(previous,condition)
                yes = self.expression_bit(args[1],index,width,signed)
                self.guard = self.circuit.AND(previous,self.circuit.NOT(condition))
                no = self.expression_bit(args[2],index,width,signed)
            finally:
                self.guard = previous
            return self.circuit.MUX(condition,yes,no)
        if op in ('unary+','unary~'):
            value = self.expression_bit(args[0],index,width,signed)
            return self.circuit.NOT(value) if op == 'unary~' else value
        if op in ('&','|','^','~^','^~'):
            a,b = (self.expression_bit(arg,index,width,signed) for arg in args)
            fn = self.circuit.AND if op == '&' else self.circuit.OR if op == '|' else self.circuit.XOR
            value = fn(a,b)
            return self.circuit.NOT(value) if op in ('~^','^~') else value
        if op in ('<<','>>','<<<','>>>'):
            amount = self.circuit.known(self.lower(args[1]))
            if amount is not None:
                source = index-amount if op in ('<<','<<<') else index+amount
                if 0 <= source < width:
                    return self.expression_bit(args[0],source,width,signed)
                return self.expression_bit(args[0],width-1,width,signed) if op == '>>>' and signed else 0
        return self.lower(expr,context,signed_context).bits[index]

    @diagnostic
    def lower(self, expr, context=0, signed_context=None):
        key = (id(expr),context,signed_context,self.guard)
        return self.cached(self.lowered,key,lambda: self._lower(expr,context,signed_context))

    def _lower(self, expr, context=0, signed_context=None):
        c = self.circuit
        op, args = expr.op, expr.args
        natural, signed = self.type_of(expr)
        # Mixed unsigned parents convert operands before any extension. The
        # destination contributes width, but never changes RHS signedness.
        signed = signed if signed_context is None else signed_context
        width = max(natural, context)
        if op in ('literal', 'signed_literal', 'unsized'):
            return resize(c.const(args[0], natural), width, signed and op != 'literal')
        if op == 'name':
            if args[0] in self.module.parameters:
                value = self.module.parameters[args[0]]
                return resize(c.const(value.bits, value.width), width, signed and value.signed)
            return resize(self.signal(args[0]), width, signed and self.module.signals[args[0]].signed)
        if op == 'captured':
            return resize(self.capture(args[0]),width,signed and args[2])
        if op == 'array_read':
            words,index_expr,_,word_signed,indices = args
            index = self.lower(index_expr)
            index_signed = self.type_of(index_expr)[1]
            output,valid = [0]*natural,0
            for word,integer in zip(words,indices):
                match = self.index_match(index,index_signed,integer)
                valid = c.OR(valid,match)
                value = self.guarded(word,match)
                output = [c.OR(old,c.AND(match,new)) for old,new in zip(output,value.bits)]
            self.flag('trap.invalid_array_index',c.NOT(valid))
            return resize(Value(tuple(output)),width,signed and word_signed)
        if op == 'typed':
            value = resize(self.lower(args[0], natural), natural)
            return resize(value,width,signed and args[2])
        if op == 'index_eq':
            index = self.lower(args[0])
            return resize(Value((self.index_match(index,self.type_of(args[0])[1],args[1]),)),width)
        if op == 'case_eq':
            operands = args[:-1]
            types = [self.type_of(a) for a in operands]
            common_width,common_signed = max(t[0] for t in types),all(t[1] for t in types)
            a,b = (self.lower(a,common_width,common_signed) for a in (operands[0],operands[args[-1]+1]))
            return resize(Value((c.eq(a,b),)),width)
        if op in ('bit_select', 'indexed_select'):
            base,index = self.lower(args[0]),self.lower(args[1])
            index_signed = self.type_of(args[1])[1]
            output,valid = [0]*natural,0
            for start in range(base.width):
                low = start if op == 'bit_select' or args[3] == '+:' else start-natural+1
                if low < 0 or low+natural > base.width: continue
                match = self.index_match(index,index_signed,start)
                valid = c.OR(valid,match)
                output = [c.OR(old,c.AND(match,new)) for old,new in zip(output,base.bits[low:low+natural])]
            self.flag('trap.invalid_select',c.NOT(valid))
            return resize(Value(tuple(output)),width)
        if op == 'select':
            value = Value(tuple(self.expression_bit(args[0],i) for i in range(args[2],args[1]+1)))
            return resize(value, width)
        if op == 'concat':
            return resize(Value(tuple(bit for a in reversed(args) for bit in self.lower(a).bits)), width)
        if op == 'repeat':
            return resize(Value(self.lower(args[1]).bits * args[0]), width)
        if op in ('signed', 'unsigned'):
            return resize(self.lower(args[0]), width, signed and op == 'signed')
        if op == '?:':
            condition = c.nonzero(self.lower(args[0]))
            yes = self.guarded(args[1],condition,width,signed)
            no = self.guarded(args[2],c.NOT(condition),width,signed)
            return c.mux(condition,yes,no)
        if op.startswith('unary'):
            operator = op[5:]
            a = self.lower(args[0]) if operator in REDUCTIONS or operator == '!' else self.lower(args[0], width, signed)
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
            a = c.nonzero(self.lower(args[0]))
            b = c.nonzero(self.guarded(args[1],a if op == '&&' else c.NOT(a)))
            return resize(Value(((c.AND if op == '&&' else c.OR)(a, b),)), width)
        if op in COMPARISONS:
            types = [self.type_of(a) for a in args]
            operand_width, operand_signed = max(t[0] for t in types), all(t[1] for t in types)
            a, b = (self.lower(a, operand_width, operand_signed) for a in args)
            if op in ('==', '!='):
                value = c.eq(a, b)
            else:
                value = c.lt(b, a, signed=operand_signed) if op in ('>', '<=') else c.lt(a, b, signed=operand_signed)
            if op in ('!=', '<=', '>='): value = c.NOT(value)
            return resize(Value((value,)), width)
        if op in ('<<', '>>', '<<<', '>>>'):
            a, amount = self.lower(args[0], width, signed), self.lower(args[1])
            fill = a.bits[-1] if op == '>>>' and signed else 0
            bits = a.bits
            # Verilog shifts do not mask the count to log2(width), unlike Wasm.
            for level, bit in enumerate(amount.bits):
                distance = 1 << level
                if distance >= width: other = (fill,)*width
                elif op in ('<<', '<<<'): other = (0,)*distance + bits[:-distance]
                else: other = bits[distance:] + (fill,)*distance
                bits = tuple(c.MUX(bit, new, old) for new, old in zip(other, bits))
            return Value(bits)
        a, b = (self.lower(a, width, signed) for a in args)
        if op in ('+', '-'): return c.add(a, b, op == '-')
        if op == '*': return c.mul(a, b)
        if op in ('/', '%'):
            self.flag('trap.integer_divide_by_zero',c.NOT(c.nonzero(b)))
            quotient,remainder = self.division.divmod(a,b,signed)
            return quotient if op == '/' else remainder
        value = c.bitwise({'&': 'and', '|': 'or', '^': 'xor', '~^': 'xor', '^~': 'xor'}[op], a, b)
        return Value(tuple(c.NOT(bit) for bit in value.bits)) if op in ('~^', '^~') else value

    def compile(self):
        # Validate and lower every driver, including unused wires, to detect
        # unsupported expressions, undeclared names and hidden cycles.
        for expr in [*self.module.captures.values(), *self.module.assignments.values(), *self.module.checks]:
            self.width(expr)
        for identifier in self.module.captures:
            previous = self.flags
            self.flags = {}
            try: self.capture(identifier)
            finally: self.flags = previous
        for name in self.module.assignments:
            self.signal(name)
        self.circuit.verilog_flags = {name:flag for name,flag in self.flags.items() if flag != 0}
        return self.circuit, [self.values[s.name] for s in self.module.outputs]


def compile_source(source, *, max_gates=12000, parameters=None, top=None, source_name="<source>"):
    source = source if isinstance(source, SourceText) else SourceText(source, source_name)
    try:
        module = Parser(source, parameters=parameters, top=top).parse()
        circuit, results = Lowerer(module, max_gates).compile()
    except RecursionError:
        raise VerilogResourceLimit('source exceeds compiler nesting capacity; reduce expression or hierarchy depth', source.location(0)) from None
    except VerilogError as error:
        raise error.at(source.location(0)) from None
    return module, circuit, results
