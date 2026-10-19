"""Reusable bit-register IR and native GSUB Boolean-circuit backend.

Each wire occupies one immutable position on a glyph tape. Gates read earlier
wires using mark-filtered chained contextual substitutions. Scratch wires start
UNINITIALIZED, never with an assumed result. No program input/output tables are
built; a gate has at most sixteen local truth-table entries.
"""
from __future__ import annotations
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Callable, Iterable
import hashlib
import json

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString


class ResourceLimit(ValueError):
    """Compilation exceeded an explicitly configured finite resource budget."""


@dataclass(frozen=True)
class Wire:
    kind: str
    sources: tuple[int, ...] = ()
    table: tuple[int, ...] = ()
    argument: int = -1
    bit: int = -1
    constant: int = 0


@dataclass(frozen=True)
class Value:
    bits: tuple[int, ...]  # little-endian wire IDs, not runtime integers

    @property
    def width(self) -> int:
        return len(self.bits)


DEFAULT_MAX_GATES = 24000
MAX_GATES = 32000


class Circuit:
    def __init__(self, max_gates: int = DEFAULT_MAX_GATES):
        if not 1 <= max_gates <= MAX_GATES:
            raise ValueError(f'max_gates must be between 1 and {MAX_GATES}')
        self.max_gates = max_gates
        self.wires = [Wire('constant', constant=0), Wire('constant', constant=1)]
        self.cache: dict[tuple, int] = {}
        self.gate_count = 0

    def const(self, value: int, width: int) -> Value:
        return Value(tuple((value >> i) & 1 for i in range(width)))

    def argument(self, index: int, width: int) -> Value:
        ids = []
        for bit in range(width):
            ids.append(len(self.wires))
            self.wires.append(Wire('argument', argument=index, bit=bit))
        return Value(tuple(ids))

    def known(self, value: Value) -> int | None:
        if all(x in (0, 1) for x in value.bits):
            return sum(x << i for i, x in enumerate(value.bits))
        return None

    def gate(self, sources: Iterable[int], fn: Callable[..., int]) -> int:
        original = tuple(sources)
        unique = tuple(sorted(set(original) - {0, 1}))
        if len(unique) > 4:
            raise ValueError('a primitive gate may read at most four dynamic bits')
        table = []
        for values in product((0, 1), repeat=len(unique)):
            env = {0: 0, 1: 1, **dict(zip(unique, values))}
            table.append(int(bool(fn(*(env[x] for x in original)))))
        # Remove irrelevant inputs, including unused arms of a constant mux.
        while True:
            removed = False
            for i in range(len(unique)):
                step = 1 << (len(unique) - 1 - i)
                if all(table[j] == table[j | step] for j in range(len(table)) if not j & step):
                    table = [table[j] for j in range(len(table)) if not j & step]
                    unique = unique[:i] + unique[i + 1:]
                    removed = True
                    break
            if not removed:
                break
        if not unique:
            return table[0]
        if len(unique) == 1 and table == [0, 1]:
            return unique[0]
        key = (unique, tuple(table))
        if key in self.cache:
            return self.cache[key]
        if self.gate_count >= self.max_gates:
            raise ResourceLimit(f'Boolean circuit exceeds max_gates={self.max_gates}')
        output = len(self.wires)
        self.wires.append(Wire('gate', unique, tuple(table)))
        self.cache[key] = output
        self.gate_count += 1
        return output

    def NOT(self, a): return self.gate((a,), lambda a: 1 - a)
    def AND(self, a, b): return self.gate((a, b), lambda a, b: a & b)
    def OR(self, a, b): return self.gate((a, b), lambda a, b: a | b)
    def XOR(self, a, b): return self.gate((a, b), lambda a, b: a ^ b)
    def MUX(self, c, a, b): return self.gate((c, a, b), lambda c, a, b: a if c else b)

    def mux(self, condition: int, yes: Value, no: Value) -> Value:
        if yes.width != no.width:
            raise ValueError('select value width mismatch')
        return Value(tuple(self.MUX(condition, a, b) for a, b in zip(yes.bits, no.bits)))

    def bitwise(self, op: str, a: Value, b: Value) -> Value:
        if a.width != b.width:
            raise ValueError('integer operand width mismatch')
        fn = {'and': self.AND, 'or': self.OR, 'xor': self.XOR}[op]
        return Value(tuple(fn(x, y) for x, y in zip(a.bits, b.bits)))

    def add(self, a: Value, b: Value, subtract: bool = False) -> Value:
        if a.width != b.width:
            raise ValueError('integer operand width mismatch')
        carry = int(subtract)
        out = []
        for x, y in zip(a.bits, b.bits):
            if subtract:
                out.append(self.gate((x, y, carry), lambda x, y, c: x ^ (1-y) ^ c))
                carry = self.gate((x, y, carry), lambda x, y, c: (x & (1-y)) | (x & c) | ((1-y) & c))
            else:
                out.append(self.gate((x, y, carry), lambda x, y, c: x ^ y ^ c))
                carry = self.gate((x, y, carry), lambda x, y, c: (x & y) | (x & c) | (y & c))
        return Value(tuple(out))

    def nonzero(self, a: Value) -> int:
        layer = list(a.bits)
        while len(layer) > 1:
            layer = [self.OR(layer[i], layer[i+1]) if i+1 < len(layer) else layer[i]
                     for i in range(0, len(layer), 2)]
        return layer[0] if layer else 0

    def add_subtract(self, a: Value, b: Value, subtract: int) -> Value:
        """Add or subtract b according to one runtime bit, without a mux per bit."""
        if a.width != b.width:
            raise ValueError('integer operand width mismatch')
        carry = subtract
        out = []
        for i, (x, y) in enumerate(zip(a.bits, b.bits)):
            sources = (x, y, carry, subtract)
            out.append(self.gate(sources, lambda x,y,c,s: x ^ y ^ s ^ c))
            if i + 1 < a.width:
                carry = self.gate(sources, lambda x,y,c,s:
                                  (x & (y ^ s)) | (x & c) | ((y ^ s) & c))
        return Value(tuple(out))

    def add_if(self, a: Value, b: Value, condition: int) -> Value:
        """Conditionally add b in paired four-input sum/carry gates."""
        if a.width != b.width:
            raise ValueError('integer operand width mismatch')
        carry = 0
        out = []
        for i, (x, y) in enumerate(zip(a.bits, b.bits)):
            sources = (x, y, carry, condition)
            out.append(self.gate(sources, lambda x,y,c,t: x ^ (y & t) ^ c))
            if i + 1 < a.width:
                carry = self.gate(sources, lambda x,y,c,t:
                                  (x & y & t) | (x & c) | (y & t & c))
        return Value(tuple(out))

    def eq(self, a: Value, b: Value) -> int:
        return self.NOT(self.nonzero(self.bitwise('xor', a, b)))

    def lt(self, a: Value, b: Value, signed: bool = False) -> int:
        if a.width != b.width:
            raise ValueError('comparison operand width mismatch')
        borrow = 0
        for i, (x, y) in enumerate(zip(a.bits, b.bits)):
            if signed and i == a.width-1:
                borrow = self.gate((x,y,borrow), lambda x,y,c: (x & (1-y)) | ((1-(x^y)) & c))
            else:
                borrow = self.gate((x,y,borrow), lambda x,y,c: ((1-x) & y) | ((1-(x^y)) & c))
        return borrow

    def compare(self, op: str, a: Value, b: Value) -> Value:
        if op in ('eq', 'ne'):
            v = self.eq(a,b)
            if op == 'ne': v = self.NOT(v)
        else:
            signed = op.endswith('_s')
            if op.startswith(('gt', 'le')): a,b = b,a
            v = self.lt(a,b,signed)
            if op.startswith(('le','ge')): v = self.NOT(v)
        return Value((v,) + (0,)*31)

    def shift(self, op: str, a: Value, b: Value) -> Value:
        width = a.width
        if width & (width-1):
            raise ValueError('barrel shifter requires a power-of-two width')
        bits = a.bits
        for level in range(width.bit_length()-1):
            distance = 1 << level
            if op == 'shl': other = (0,)*distance + bits[:-distance]
            elif op == 'shr_u': other = bits[distance:] + (0,)*distance
            elif op == 'shr_s': other = bits[distance:] + (bits[-1],)*distance
            elif op == 'rotl': other = bits[-distance:] + bits[:-distance]
            elif op == 'rotr': other = bits[distance:] + bits[:distance]
            else: raise ValueError(op)
            bits = tuple(self.MUX(b.bits[level], new, old) for new,old in zip(other,bits))
        return Value(bits)

    def mul(self, a: Value, b: Value) -> Value:
        """Truncated multiplication with partial products fused into the adder.

        A row adds (a & multiplier_bit) at its bit offset. Four-input gates
        compute sum/carry directly, without storing a separate AND wire for
        each partial product. The completed low bits bypass subsequent rows.
        """
        if a.width != b.width:
            raise ValueError('integer operand width mismatch')
        acc = self.const(0,a.width)
        for i, bit in enumerate(b.bits):
            tail = self.add_if(Value(acc.bits[i:]), Value(a.bits[:a.width-i]), bit)
            acc = Value(acc.bits[:i] + tail.bits)
        return acc

    def count(self, op: str, a: Value) -> Value:
        n = a.width.bit_length()
        count = self.const(0,n)
        seen = 0
        bits = a.bits[::-1] if op == 'clz' else a.bits
        for bit in bits:
            if op == 'popcnt': inc = bit
            else:
                seen = self.OR(seen,bit)
                inc = self.NOT(seen)
            count = self.add(count, Value((inc,) + (0,)*(n-1)))
        return Value(count.bits + (0,)*(a.width-n))


    def unsigned_divmod(self, a: Value, b: Value) -> tuple[Value,Value]:
        """Integer division; the calling frontend supplies its error predicates."""
        if a.width != b.width: raise ValueError('division width mismatch')
        width=a.width
        # Exact wire identities, not runtime-value specialization. These
        # eliminate a quadratic divider while retaining the caller's trap
        # predicate for a zero divisor.
        known_divisor=self.known(b)
        if known_divisor == 1:
            return a, self.const(0,width)
        if self.known(a) == 0:
            return self.const(0,width), self.const(0,width)
        if a.bits == b.bits:
            return self.const(1,width), self.const(0,width)
        # A zero-extended narrow calculation needs only its live low bits.
        # This is structural specialization: inspect constant wire IDs, never
        # runtime arguments or precomputed input/output pairs.
        active=width
        while active>1 and a.bits[active-1]==0 and b.bits[active-1]==0:
            active-=1
        if active<width:
            q,r=self.unsigned_divmod(Value(a.bits[:active]),Value(b.bits[:active]))
            padding=(0,)*(width-active)
            return Value(q.bits+padding),Value(r.bits+padding)
        if known_divisor is None:
            return self._restoring_divmod(a, b)
        # For a nonzero constant d, each completed step has 0 <= r < d.
        # The next shifted remainder needs only d.bit_length() + 1 bits,
        # even when the dividend is a full-width i64. This is a bound on
        # intermediate wires, not a specialization on invocation arguments.
        remainder_width=known_divisor.bit_length() if known_divisor else width
        remainder=self.const(0,remainder_width+1)
        divisor=Value(b.bits[:remainder_width]+(0,))
        quotient=[0]*width
        for i in reversed(range(width)):
            remainder=Value((a.bits[i],)+remainder.bits[:remainder_width])
            take=self.NOT(self.lt(remainder,divisor))
            remainder=self.mux(take,self.add(remainder,divisor,True),remainder)
            quotient[i]=take
        return Value(tuple(quotient)),Value(remainder.bits[:remainder_width]+(0,)*(width-remainder_width))

    def _restoring_divmod(self, a: Value, b: Value) -> tuple[Value,Value]:
        """Grow the remainder one bit per step and fuse subtraction/selection.

        After k dividend bits, the remainder fits k bits. A divisor with any
        nonzero bit above k cannot be subtracted; suffix ORs detect that case.
        Compute borrows first, then choose each difference bit directly in a
        four-input gate, without separate difference and mux registers. The
        last borrow and the high-divisor test fold into the quotient decision;
        its matching top remainder gate shares the same four inputs.
        """
        width = a.width
        high = [0] * (width + 1)
        for i in reversed(range(1,width)):
            high[i] = self.OR(b.bits[i], high[i + 1])
        remainder = Value(())
        quotient = [0] * width
        borrow_out = lambda x,y,c: ((1-x) & (y | c)) | (y & c)
        for k,i in enumerate(reversed(range(width)),1):
            shifted = Value((a.bits[i],) + remainder.bits)
            borrows = [0]
            for x,y in zip(shifted.bits[:-1],b.bits):
                borrows.append(self.gate((x,y,borrows[-1]),borrow_out))
            top = (shifted.bits[-1],b.bits[k-1],borrows[-1],high[k])
            take = self.gate(top,lambda x,y,c,h: not (h or borrow_out(x,y,c)))
            quotient[i] = take
            low = tuple(self.gate((x,y,c,take),lambda x,y,c,t: (x ^ y ^ c) if t else x)
                        for x,y,c in zip(shifted.bits[:-1],b.bits,borrows))
            last = self.gate(top,lambda x,y,c,h:
                             x if h or borrow_out(x,y,c) else x ^ y ^ c)
            remainder = Value(low + (last,))
        return Value(tuple(quotient)), remainder

    def materialize(self, value: Value) -> Value:
        """Copy to canonical output cells inside GSUB, never in the host decoder."""
        outputs=[]
        for source in value.bits:
            if self.gate_count >= self.max_gates:
                raise ResourceLimit(f'output materialization exceeds max_gates={self.max_gates}')
            outputs.append(len(self.wires))
            self.wires.append(Wire('gate',(source,),(0,1)))
            self.gate_count+=1
        return Value(tuple(outputs))

    def reachable(self, outputs: Iterable[int]) -> list[int]:
        live = {i for i,wire in enumerate(self.wires) if wire.kind == 'argument'}
        todo = list(outputs)
        while todo:
            i = todo.pop()
            if i in live: continue
            live.add(i)
            todo.extend(self.wires[i].sources)
        return sorted(live)

    def evaluate_for_test(self, args: list[int]) -> list[int]:
        """Circuit oracle for exhaustive unit tests; NEVER called by the shaper."""
        values = []
        for wire in self.wires:
            if wire.kind == 'constant': v = wire.constant
            elif wire.kind == 'argument': v = (args[wire.argument] >> wire.bit) & 1
            else:
                index = 0
                for source in wire.sources: index = (index << 1) | values[source]
                v = wire.table[index]
            values.append(v)
        return values


def glyph(wire: int, value: int | str) -> str:
    return f'w{wire}_{value}'


def emit_font(circuit: Circuit, results: list[Value], flags: dict[str,int],
              parameter_types: list[str], result_types: list[str], path: str | Path,
              *, extra: dict | None = None, lookup_batch_size: int | None = None,
              lookup_coalescing: bool | None = None,
              font_family: str | None = None) -> dict:
    """Emit ordered gate lookups and an ABI manifest.

    lookup_coalescing=None tries separate subtables before sharing adjacent
    groups; True forces the shared tier and False disables it.
    """
    results=[circuit.materialize(value) for value in results]
    flags={name:circuit.materialize(Value((wire,))).bits[0] for name,wire in flags.items()}
    roots = [bit for value in results for bit in value.bits] + list(flags.values())
    live = circuit.reachable(roots)
    names = ['.notdef','space']
    for i in live:
        names.extend((glyph(i,0),glyph(i,1)))
        if circuit.wires[i].kind == 'gate': names.append(glyph(i,'u'))
    if len(names) >= 65535:
        raise ResourceLimit('OpenType glyph-count limit exceeded')
    # Machine registers use empty glyph outlines and a fixed PUA mapping.
    fb = FontBuilder(1000,isTTF=True)
    fb.setupGlyphOrder(names)
    fb.setupCharacterMap({32:'space', **{0xF0000+i:name for i,name in enumerate(names[2:])}})
    fb.setupGlyf({name:TTGlyphPen(None).glyph() for name in names})
    fb.setupHorizontalMetrics({name:(0,0) for name in names})
    fb.setupHorizontalHeader(ascent=800,descent=-200)
    font_names = {'familyName':'Wasm GSUB Registers','styleName':'Regular',
                      'uniqueFontIdentifier':'wasm-gsub-registers-v1',
                      'fullName':'Wasm GSUB Registers','psName':'WasmGSUBRegisters'}
    if font_family is not None:
        font_names.update(familyName=font_family, fullName=font_family,
                          uniqueFontIdentifier=font_family.replace(' ', '') + '-v1',
                          psName=font_family.replace(' ', ''),
                          copyright='Copyright 2026 Michael Brackx',
                          licenseDescription='Licensed under the Apache License, Version 2.0.',
                          licenseInfoURL='https://www.apache.org/licenses/LICENSE-2.0')
    fb.setupNameTable(font_names)
    fb.setupOS2(sTypoAscender=800,sTypoDescender=-200,usWinAscent=800,usWinDescent=200)
    fb.setupPost(); fb.setupMaxp()
    fb.font['head'].created=fb.font['head'].modified=2082844800
    fb.font.recalcTimestamp=False
    from .tables import attach_tables
    gates,lookup_count,packing=attach_tables(fb.font,circuit,live,names,batch_size=lookup_batch_size,
                                           coalesce=lookup_coalescing)
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    try:
        fb.save(str(path))
    except Exception as exc:
        from fontTools.ttLib.tables.otBase import OTLOffsetOverflowError
        if isinstance(exc, (OTLOffsetOverflowError, RecursionError)):
            raise ResourceLimit('font layout capacity exceeded; reduce compilation bounds') from exc
        raise
    manifest = {
        'abi':'wasm-gsub-registers-v1', 'parameter_types':parameter_types,
        'result_types':result_types, 'tape':[
            {'wire':i,'kind':circuit.wires[i].kind,'argument':circuit.wires[i].argument,
             'bit':circuit.wires[i].bit,'constant':circuit.wires[i].constant} for i in live],
        'results':[list(value.bits) for value in results], 'flags':flags,
        'metrics':{'wires':len(live),'gates':gates,'glyphs':len(names),
                   'lookups':lookup_count,'font_bytes':path.stat().st_size,**packing},
        'font_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    if extra: manifest.update(extra)
    path.with_suffix('.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest
