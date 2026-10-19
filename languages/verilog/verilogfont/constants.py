# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Typed compile-time expressions; no runtime circuit inputs enter this layer."""
from dataclasses import dataclass
from .syntax import Constant, Expr, VerilogError, MAX_DEPTH, MAX_WIDTH, diagnostic, VerilogResourceLimit, operator_type


@dataclass(frozen=True)
class ParameterDecl:
    name: str
    expression: Expr
    bounds: tuple[Expr, Expr] | None = None
    local: bool = False
    signed: bool = False


class ConstantEvaluator:
    def __init__(self, declarations, overrides):
        self.declarations = declarations
        self.overrides = overrides
        self.values = {}
        self.visiting = set()
        self.types = {}
        for name in overrides:
            if name not in declarations:
                raise VerilogError(f'unknown parameter override: {name}')
            if declarations[name].local:
                raise VerilogError(f'cannot override localparam: {name}')

    def parameter(self, name):
        if name in self.values:
            return self.values[name]
        if name not in self.declarations:
            raise VerilogError(f'constant expression references non-parameter: {name}')
        if name in self.visiting:
            raise VerilogError(f'parameter dependency cycle involving {name}')
        if len(self.visiting) >= MAX_DEPTH:
            raise VerilogResourceLimit(f'parameter dependency depth exceeds {MAX_DEPTH}')
        self.visiting.add(name)
        declaration = self.declarations[name]
        width = self.range_width(declaration.bounds) if declaration.bounds is not None else 0
        expression = self.overrides.get(name, declaration.expression)
        value = self.evaluate(expression, width)
        if width or declaration.signed:
            width = width or value.width
            value = Constant(value.bits & ((1 << width)-1), width, declaration.signed)
        self.values[name] = value
        self.visiting.remove(name)
        return value

    def range_width(self, bounds):
        high, low = (self.evaluate(expr).integer for expr in bounds)
        if low != 0 or not 0 <= high < MAX_WIDTH:
            raise VerilogError(f'ranges must be descending [N:0], with width 1–{MAX_WIDTH}')
        return high + 1

    def select_bounds(self, base, high, low):
        high = high if type(high) is int else self.evaluate(high).integer
        low = low if type(low) is int else self.evaluate(low).integer
        if not 0 <= low <= high < self.type_of(base)[0]:
            raise VerilogError('constant bit/part select is outside its parameter range')
        return high, low

    def indexed_bounds(self, base, index, width, direction):
        index = self.evaluate(index).integer
        width = self.evaluate(width).integer
        low = index if direction == '+:' else index-width+1
        high = low+width-1
        if not 1 <= width <= MAX_WIDTH or not 0 <= low <= high < self.type_of(base)[0]:
            raise VerilogError('constant indexed part select is outside its parameter range')
        return high,low

    def repeat_count(self, expression):
        count = expression if type(expression) is int else self.evaluate(expression).integer
        if not 1 <= count <= MAX_WIDTH:
            raise VerilogError(f'repeat count must be 1–{MAX_WIDTH}')
        return count

    @diagnostic
    def type_of(self, expr, depth=0):
        if depth >= MAX_DEPTH:
            raise VerilogResourceLimit(f'constant expression depth exceeds {MAX_DEPTH}')
        if id(expr) in self.types:
            return self.types[id(expr)]
        op, args = expr.op, expr.args
        if op in ('literal', 'signed_literal', 'unsized'):
            result = (args[1], op != 'literal')
        elif op == 'call':
            raise VerilogError('user functions are supported in runtime expressions, not parameter/range constants')
        elif op == 'name':
            value = self.parameter(args[0])
            result = (value.width, value.signed)
        elif op == 'indexed':
            high, low = self.indexed_bounds(*args)
            result = (high-low+1, False)
        elif op == 'select':
            high, low = self.select_bounds(*args)
            result = (high-low+1, False)
        elif op == 'concat':
            result = (sum(self.type_of(a, depth+1)[0] for a in args), False)
        elif op == 'repeat':
            result = (self.repeat_count(args[0])*self.type_of(args[1], depth+1)[0], False)
        elif op == 'clog2':
            self.type_of(args[0], depth+1)
            result = (32, True)
        else:
            types = [self.type_of(a, depth+1) for a in args]
            result = operator_type(op, types)
        if not 1 <= result[0] <= MAX_WIDTH:
            raise VerilogError(f'constant expression width exceeds {MAX_WIDTH} bits')
        self.types[id(expr)] = result
        return result

    @diagnostic
    def evaluate(self, expr, context=0, signed_context=None):
        natural, signed = self.type_of(expr)
        width = max(natural, context)
        signed = signed if signed_context is None else signed_context
        op, args = expr.op, expr.args

        def value(bits, own_width=width, own_signed=signed):
            return Constant(bits & ((1 << own_width)-1), own_width, own_signed)

        def extend(result):
            return result.resized(width, signed)

        if op in ('literal', 'signed_literal', 'unsized'):
            return extend(Constant(args[0], args[1], op != 'literal'))
        if op == 'name':
            return extend(self.parameter(args[0]))
        if op in ('select', 'indexed'):
            high, low = self.select_bounds(*args) if op == 'select' else self.indexed_bounds(*args)
            result = self.evaluate(args[0]).bits >> low
            return extend(value(result, high-low+1, False))
        if op == 'concat':
            bits = 0
            for arg in args:
                part = self.evaluate(arg)
                # Unsized expressions cannot be concatenation operands in Verilog.
                if ConstantEvaluator.contains_unsized(arg):
                    raise VerilogError('unsized literals are unsupported in concatenations')
                bits = (bits << part.width) | part.bits
            return extend(value(bits, natural, False))
        if op == 'repeat':
            count, part = self.repeat_count(args[0]), self.evaluate(args[1])
            bits = 0
            for _ in range(count):
                bits = (bits << part.width) | part.bits
            return extend(value(bits, natural, False))
        if op in ('signed', 'unsigned'):
            part = self.evaluate(args[0])
            return extend(value(part.bits, part.width, op == 'signed'))
        if op == 'clog2':
            argument = self.evaluate(args[0]).integer
            if argument < 0:
                raise VerilogError('$clog2 requires a nonnegative constant')
            return extend(value((argument-1).bit_length() if argument > 1 else 0, 32, True))
        if op == '?:':
            # Both branches contribute their types, but only the selected
            # expression contributes a value (e.g. a guarded division).
            selected = args[1] if self.evaluate(args[0]).bits else args[2]
            return self.evaluate(selected, width, signed)
        if op.startswith('unary'):
            operator = op[5:]
            if operator in ('+', '-', '~'):
                a = self.evaluate(args[0], width, signed).bits
                return value(a if operator == '+' else -a if operator == '-' else ~a)
            a = self.evaluate(args[0])
            if operator == '!': result = not a.bits
            elif operator in ('&', '~&'): result = a.bits == (1 << a.width)-1
            elif operator in ('|', '~|'): result = bool(a.bits)
            else: result = bool(a.bits.bit_count() % 2)
            if operator in ('~&', '~|', '~^', '^~'): result = not result
            return extend(value(int(result), 1, False))
        if op in ('&&', '||'):
            a = bool(self.evaluate(args[0]).bits)
            result = a and bool(self.evaluate(args[1]).bits) if op == '&&' else a or bool(self.evaluate(args[1]).bits)
            return extend(value(int(result), 1, False))
        if op in ('==', '!=', '<', '<=', '>', '>='):
            types = [self.type_of(a) for a in args]
            operand_width, operand_signed = max(t[0] for t in types), all(t[1] for t in types)
            a, b = (self.evaluate(a, operand_width, operand_signed).integer for a in args)
            result = {'==': a == b, '!=': a != b, '<': a < b, '<=': a <= b,
                      '>': a > b, '>=': a >= b}[op]
            return extend(value(int(result), 1, False))
        if op in ('<<', '>>', '<<<', '>>>'):
            left = self.evaluate(args[0], width, signed)
            a = left.integer if op == '>>>' and signed else left.bits
            count = self.evaluate(args[1]).bits
            if count >= width:
                return value(-1 if a < 0 else 0)
            return value(a << count if op in ('<<', '<<<') else a >> count)
        a, b = (self.evaluate(a, width, signed) for a in args)
        if op == '+': result = a.bits + b.bits
        elif op == '-': result = a.bits - b.bits
        elif op == '*': result = a.bits * b.bits
        elif op in ('/', '%'):
            dividend, divisor = a.integer, b.integer
            if divisor == 0:
                raise VerilogError('division by zero in constant expression')
            quotient = abs(dividend)//abs(divisor)
            if (dividend < 0) != (divisor < 0): quotient = -quotient
            result = quotient if op == '/' else dividend - quotient*divisor
        elif op == '&': result = a.bits & b.bits
        elif op == '|': result = a.bits | b.bits
        elif op == '^': result = a.bits ^ b.bits
        elif op in ('~^', '^~'): result = ~(a.bits ^ b.bits)
        else: raise VerilogError(f'unsupported constant operator: {op}')
        return value(result)

    @staticmethod
    def contains_unsized(expr):
        # Self-determined operands cannot make the surrounding value indefinite.
        if expr.op == 'unsized': return True
        if expr.op in ('select', 'indexed', 'clog2', 'signed', 'unsigned', 'typed',
                       '==', '!=', '<', '<=', '>', '>=', '&&', '||'): return False
        if expr.op in ('<<', '>>', '<<<', '>>>'):
            return ConstantEvaluator.contains_unsized(expr.args[0])
        if expr.op == '?:':
            return any(ConstantEvaluator.contains_unsized(a) for a in expr.args[1:])
        if expr.op == 'repeat': return ConstantEvaluator.contains_unsized(expr.args[1])
        # Parameter names have a declared/elaborated width, unlike raw literals.
        return any(ConstantEvaluator.contains_unsized(a) for a in expr.args if isinstance(a, Expr))
