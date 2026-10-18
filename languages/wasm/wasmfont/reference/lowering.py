"""Verified lowering of a small, genuine Wasm stack expression to GSUB stages.

Only accept operations for which the font implements the same semantics. All
other programs fail closed; never substitute host evaluation for font execution.
"""
from dataclasses import dataclass
from ..frontend import load
from .pipeline import build_not_pipeline, decode_not
from .compiler import encode

@dataclass(frozen=True)
class Lowered:
    operation: str
    width: int
    inversions: int
    swapped: bool = False
    input_mode: str = "normal"
    literal: int = 0
    def build(self, path):
        return build_not_pipeline(path, self.operation, self.width, self.inversions)
    def encode(self, a, b):
        if self.input_mode.startswith("param_literal_"):
            param = a if self.input_mode.split("_")[2] == "0" else b
            reverse = self.input_mode.endswith("_reverse")
            return encode(self.literal, param, self.operation, self.width) if reverse else encode(param, self.literal, self.operation, self.width)
        if self.input_mode == "constant": return encode(0, self.literal, "xor", self.width)
        if self.input_mode == "param0_xor_const": return encode(a, self.literal, "xor", self.width)
        if self.input_mode == "param1_xor_const": return encode(b, self.literal, "xor", self.width)
        if self.input_mode == "zero": return encode(a, a, "xor", self.width)
        if self.input_mode == "double0": return encode(a, a, "add", self.width)
        if self.input_mode == "double1": return encode(b, b, "add", self.width)
        if self.input_mode == "param0": return encode(a, 0, "xor", self.width)
        if self.input_mode == "param1": return encode(b, 0, "xor", self.width)
        return encode(b, a, self.operation, self.width) if self.swapped else encode(a, b, self.operation, self.width)
    def decode(self, tokens):
        return decode_not(tokens, self.width, self.inversions)


def lower_function(fn):
    """Symbolically execute stack code and match a native GSUB implementation.

    Supported: two parameters of one integer type; one binary operation;
    subsequent XOR with all-one constants (bitwise NOT). Local variables
    can be used to move intermediate values without changing semantics.
    """
    if len(fn.params) != 2 or fn.params[0] != fn.params[1] or fn.results != [fn.params[0]]:
        raise NotImplementedError('requires two same-width params and one same-width result')
    ty = fn.params[0]
    if ty not in ('i32', 'i64'):
        raise NotImplementedError('unsupported value type')
    width = int(ty[1:]); mask = (1 << width) - 1
    stack = []
    locals_ = [('param', i) for i in range(2)] + [('const', 0)] * len(fn.locals)
    if any(t != ty for t in fn.locals):
        raise NotImplementedError('mixed-width locals')
    def simplify(operation, left, right):
        # Algebraic identities valid for fixed-width Wasm integers.
        # Only transform symbolic expressions; never evaluate runtime operands.
        if left[0] == 'const' and right[0] == 'const':
            a, b = left[1], right[1]
            return ('const', {'add': a + b, 'sub': a - b, 'and': a & b,
                              'or': a | b, 'xor': a ^ b}[operation] & mask)
        if left == right and operation in ('sub', 'xor'):
            return ('const', 0)
        if left == right and operation in ('and', 'or'):
            return left
        # Repeated dynamic operands require no additional input register: feed
        # the same runtime parameter into both GSUB adder input lanes.
        if left == right and operation == 'add' and left[0] == 'param':
            return ('double', left[1])
        # A result and its complement are represented by the same native
        # circuit with opposite inversion parity. These identities are valid
        # for every bit of both i32 and i64, including wrapping boundaries.
        if (left[0] == right[0] == 'result'
                and left[1] == right[1] and left[3:] == right[3:]
                and (left[2] - right[2]) % 2):
            if operation == 'and': return ('const', 0)
            if operation in ('or', 'xor'): return ('const', mask)
        # Normalize affine chains over the Wasm wrapping integer ring.
        # A sign of -1 means C - parameter; +1 means parameter + C.
        # This supports arbitrary-length addition/subtraction chains without
        # pretending that intermediate arithmetic is performed by Python.
        if operation in ('add', 'sub'):
            def affine(node):
                if node[0] == 'param': return (node[1], 1, 0)
                if node[0] == 'affine': return node[1:]
                if node[0] == 'literal_binary' and node[1] in ('add', 'sub'):
                    _, op, idx, c, reverse = node
                    if op == 'add': return (idx, 1, c)
                    return (idx, -1 if reverse else 1, c if reverse else -c)
                return None
            l, r = affine(left), affine(right)
            if l is not None and r is not None and l[0] == r[0]:
                idx = l[0]
                coeff = l[1] + (r[1] if operation == 'add' else -r[1])
                offset = (l[2] + (r[2] if operation == 'add' else -r[2])) & mask
                if coeff == 0: return ('const', offset)
                if coeff in (-1, 1): return ('affine', idx, coeff, offset)
                if coeff == 2 and offset == 0: return ('double', idx)
            # Cancel two affine expressions of the same runtime parameter.
            # The variable coefficients cancel modulo 2**width, leaving a
            # compile-time constant, or a doubled parameter coefficient.
            if l is not None and r is not None and l[0] == r[0]:
                coefficient = l[1] + (r[1] if operation == 'add' else -r[1])
                constant = (l[2] + (r[2] if operation == 'add' else -r[2])) & mask
                if coefficient == 0:
                    return ('const', constant)
                # Keep unsupported coefficients explicit: never pretend a
                # composed runtime arithmetic expression is native GSUB.
            if l is not None and right[0] == 'const':
                idx, sign, c = l
                return ('affine', idx, sign, (c + (right[1] if operation == 'add' else -right[1])) & mask)
            if operation == 'add' and left[0] == 'const' and r is not None:
                idx, sign, c = r
                return ('affine', idx, sign, (c + left[1]) & mask)
            if operation == 'sub' and left[0] == 'const' and r is not None:
                idx, sign, c = r
                return ('affine', idx, -sign, (left[1] - c) & mask)
        # Fuse successive literal XORs into a single native XOR circuit.
        # This is algebraic specialization, not host evaluation of parameters.
        if operation == 'xor':
            if left[0] == 'literal_xor' and right[0] == 'const':
                return ('literal_xor', left[1], (left[2] ^ right[1]) & mask)
            if right[0] == 'literal_xor' and left[0] == 'const':
                return ('literal_xor', right[1], (right[2] ^ left[1]) & mask)
            if left[0] == right[0] == 'literal_xor' and left[1] == right[1]:
                return ('const', (left[2] ^ right[2]) & mask)
            if left[0] == 'literal_xor' and right == ('param', left[1]):
                return ('const', left[2])
            if right[0] == 'literal_xor' and left == ('param', right[1]):
                return ('const', right[2])
        # Track NOT stages, including after local.tee.
        # Parity is used to recognize complementary expressions.
        # A direct parameter complement can be executed by an identity XOR
        # circuit followed by the same native inversion stage used for results.
        if operation in ('add', 'sub', 'and', 'or') and left[0] == 'param' and right[0] == 'const':
            return ('literal_binary', operation, left[1], right[1], False)
        if operation in ('add', 'sub', 'and', 'or') and right[0] == 'param' and left[0] == 'const':
            return ('literal_binary', operation, right[1], left[1], operation == 'sub')
        if operation == 'xor' and right[0] == 'const' and left[0] == 'param' and right[1] != mask:
            return ('literal_xor', left[1], right[1])
        if operation == 'xor' and left[0] == 'const' and right[0] == 'param' and left[1] != mask:
            return ('literal_xor', right[1], left[1])
        if operation == 'xor' and right == ('const', mask) and left[0] == 'param':
            return ('result', 'xor', 1, False, 'param' + str(left[1]))
        if operation == 'xor' and left == ('const', mask) and right[0] == 'param':
            return ('result', 'xor', 1, False, 'param' + str(right[1]))
        if operation == 'xor' and right == ('const', mask) and left[0] == 'result':
            return ('result', left[1], left[2] + 1, *left[3:])
        if operation == 'xor' and left == ('const', mask) and right[0] == 'result':
            return ('result', right[1], right[2] + 1, *right[3:])
        if operation in ('xor', 'or', 'add'):
            if right == ('const', 0): return left
            if left == ('const', 0): return right
        if operation in ('sub', 'and') and right == ('const', 0):
            return left if operation == 'sub' else ('const', 0)
        if operation == 'and' and left == ('const', 0): return ('const', 0)
        if operation == 'and':
            if left == ('const', mask): return right
            if right == ('const', mask): return left
        if operation == 'or':
            if left == ('const', mask) or right == ('const', mask): return ('const', mask)
        if left == ('param', 0) and right == ('param', 1):
            return ('result', operation, 0, False)
        if left == ('param', 1) and right == ('param', 0):
            return ('result', operation, 0, True)
        raise NotImplementedError('GSUB cannot yet compose this binary expression')

    for op, arg in fn.code:
        if op == 'local.get':
            if not 0 <= arg < len(locals_): raise ValueError('invalid local index')
            stack.append(locals_[arg])
        elif op in ('local.set', 'local.tee'):
            if not 0 <= arg < len(locals_) or not stack: raise ValueError('invalid local assignment')
            locals_[arg] = stack[-1] if op == 'local.tee' else stack.pop()
        elif op == ty + '.const':
            stack.append(('const', arg & mask))
        elif op in tuple(ty + '.' + x for x in ('add', 'sub', 'and', 'or', 'xor')):
            if len(stack) < 2: raise ValueError('stack underflow')
            right = stack.pop(); left = stack.pop(); operation = op.split('.')[1]
            stack.append(simplify(operation, left, right))
        elif op == ty + '.mul':
            if len(stack) < 2: raise ValueError('stack underflow')
            right = stack.pop(); left = stack.pop()
            if left[0] == right[0] == 'const':
                stack.append(('const', (left[1] * right[1]) & mask))
            else:
                constant, operand = (left, right) if left[0] == 'const' else (right, left)
                if constant[0] != 'const':
                    raise NotImplementedError('native multiplication of two dynamic operands')
                multiplier = constant[1]
                if multiplier == 0:
                    stack.append(('const', 0))
                elif multiplier == 1:
                    stack.append(operand)
                elif multiplier == 2 and operand[0] == 'param':
                    stack.append(('double', operand[1]))
                elif multiplier == mask and operand[0] == 'param':
                    stack.append(('affine', operand[1], -1, 0))
                else:
                    raise NotImplementedError('native multiplication supports constants 0, 1, 2, and -1 only')
        elif op == ty + '.shl':
            if len(stack) < 2: raise ValueError('stack underflow')
            shift = stack.pop(); operand = stack.pop()
            if shift[0] != 'const':
                raise NotImplementedError('dynamic shifts require a native barrel shifter')
            amount = shift[1] & (width - 1)
            if amount == 0:
                stack.append(operand)
            elif amount == 1 and operand[0] == 'param':
                # Wasm x << 1 is exactly wrapping x + x. The addition
                # remains a native GSUB circuit, not host preprocessing.
                stack.append(('double', operand[1]))
            elif operand[0] == 'const':
                stack.append(('const', (operand[1] << amount) & mask))
            else:
                raise NotImplementedError('native shift only supports constant 0/1 for dynamic operands')
        elif op in (ty + '.shr_u', ty + '.shr_s', ty + '.rotl', ty + '.rotr'):
            if len(stack) < 2: raise ValueError('stack underflow')
            amount_node = stack.pop(); operand = stack.pop()
            if amount_node[0] != 'const':
                raise NotImplementedError('dynamic shift/rotation requires a GSUB barrel shifter')
            amount = amount_node[1] & (width - 1)
            if amount == 0:
                stack.append(operand)
            elif operand[0] == 'const':
                v = operand[1]
                if op.endswith('shr_u'): result = v >> amount
                elif op.endswith('shr_s'):
                    signed = v if v < (1 << (width - 1)) else v - (1 << width)
                    result = signed >> amount
                elif op.endswith('rotl'):
                    result = (v << amount) | (v >> (width - amount))
                else:
                    result = (v >> amount) | (v << (width - amount))
                stack.append(('const', result & mask))
            else:
                raise NotImplementedError('nonzero dynamic-value shift/rotation not yet native')
        elif op in (ty + '.clz', ty + '.ctz', ty + '.popcnt'):
            if not stack: raise ValueError('stack underflow')
            operand = stack.pop()
            if operand[0] != 'const':
                raise NotImplementedError('counting dynamic values requires native counting lowering')
            v = operand[1]
            if op.endswith('clz'): result = width - v.bit_length()
            elif op.endswith('ctz'): result = width if v == 0 else (v & -v).bit_length() - 1
            else: result = v.bit_count()
            stack.append(('const', result))
        elif op == ty + '.eqz':
            if not stack: raise ValueError('stack underflow')
            operand = stack.pop()
            if operand[0] != 'const':
                raise NotImplementedError('dynamic eqz needs a native reduction circuit')
            stack.append(('const', int(operand[1] == 0)))
        elif op == 'drop':
            if not stack: raise ValueError('stack underflow')
            stack.pop()
        elif op == 'select':
            if len(stack) < 3: raise ValueError('stack underflow')
            condition = stack.pop(); false_value = stack.pop(); true_value = stack.pop()
            if condition[0] == 'const':
                stack.append(true_value if condition[1] else false_value)
            elif true_value == false_value:
                stack.append(true_value)
            else:
                raise NotImplementedError('dynamic select requires a GSUB multiplexer')
        elif op == 'nop':
            pass
        elif op == 'return':
            break
        else:
            raise NotImplementedError(f'unsupported native GSUB instruction: {op}')
    if len(stack) != 1: raise NotImplementedError('unsupported stack result')
    value = stack[0]
    if value[0] == 'double':
        return Lowered('add', width, 0, False, 'double' + str(value[1]))
    if value[0] == 'affine':
        _, idx, sign, c = value
        if sign == 1:
            return Lowered('add', width, 0, False, f'param_literal_{idx}', c)
        return Lowered('sub', width, 0, False, f'param_literal_{idx}_reverse', c)
    if value[0] == 'literal_binary':
        return Lowered(value[1], width, 0, False, f'param_literal_{value[2]}' + ('_reverse' if value[4] else ''), value[3])
    if value[0] == 'literal_xor':
        return Lowered('xor', width, 0, False, f'param{value[1]}_xor_const', value[2])
    if value[0] == 'const' and value[1] not in (0, mask):
        return Lowered('xor', width, 0, False, 'constant', value[1])
    if value[0] == 'result':
        return Lowered(value[1], width, value[2], value[3], value[4] if len(value) > 4 else 'normal')
    # Constant zero/all-ones and parameter passthrough are still executed
    # by real GSUB XOR gates. Runtime values are never precomputed.
    if value == ('const', 0): return Lowered('xor', width, 0, False, 'zero')
    if value == ('const', mask): return Lowered('xor', width, 1, False, 'zero')
    if value == ('param', 0): return Lowered('xor', width, 0, False, 'param0')
    if value == ('param', 1): return Lowered('xor', width, 0, False, 'param1')
    raise NotImplementedError('unsupported symbolic output')


def compile_module(source, font_path, function_index=0):
    module, _ = load(source)
    functions = module.functions
    if not 0 <= function_index < len(functions): raise ValueError('function index out of range')
    result = lower_function(functions[function_index]); result.build(font_path)
    return result
