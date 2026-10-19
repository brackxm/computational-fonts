# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Finite Verilog division circuits; operands are wires, never invocation values."""
from fontcircuit.gsub.circuit import Value


class Division:
    def __init__(self, circuit):
        self.circuit = circuit
        self.results = {}

    def divmod(self, a, b, signed):
        key = (a.bits,b.bits,signed)
        if key not in self.results:
            self.results[key] = self._divmod(a,b,signed)
        return self.results[key]

    def _divmod(self, a, b, signed):
        c, width = self.circuit, a.width
        zero = c.const(0,width)
        divisor = c.known(b)
        if divisor == 0 or c.known(a) == 0:
            # The caller retains a predicate for a zero divisor, even when the
            # result wires are constant or the operation is otherwise an identity.
            return zero,zero
        if a.bits == b.bits:
            return c.const(1,width),zero
        if signed:
            # Repeated sign wires bound both operands structurally. Retain one
            # extra bit so a widened MIN / -1 can produce its positive result.
            active = width
            while active > 1 and a.bits[active-1] == a.bits[active-2] and b.bits[active-1] == b.bits[active-2]:
                active -= 1
            narrowed = active+1
            if narrowed < width:
                q,r = self.divmod(Value(a.bits[:narrowed]),Value(b.bits[:narrowed]),True)
                return (Value(q.bits+(q.bits[-1],)*(width-narrowed)),
                        Value(r.bits+(r.bits[-1],)*(width-narrowed)))
        integer = divisor-(1 << width) if signed and divisor is not None and divisor & (1 << (width-1)) else divisor
        magnitude = abs(integer) if integer is not None else None
        if magnitude is not None and magnitude > 0 and magnitude & (magnitude-1) == 0:
            distance = magnitude.bit_length()-1
            if not signed:
                return Value(a.bits[distance:]+(0,)*distance),Value(a.bits[:distance]+(0,)*(width-distance))
            # Bias an arithmetic shift to truncate negative quotients toward
            # zero, rather than toward minus infinity.
            negative = a.bits[-1]
            bias = Value((negative,)*distance+(0,)*(width-distance))
            adjusted = c.add(a,bias) if distance else a
            quotient = Value(adjusted.bits[distance:]+(adjusted.bits[-1],)*distance)
            if integer < 0:
                quotient = c.add(zero,quotient,True)
            # A signed power-of-two remainder keeps the low bits of a and
            # sign-extends only when those low bits are nonzero.
            low = Value(a.bits[:distance])
            fill = c.AND(negative,c.nonzero(low))
            remainder = Value(low.bits+(fill,)*(width-distance))
            return quotient,remainder
        if not signed:
            return c.unsigned_divmod(a,b)
        negative_a,negative_b = a.bits[-1],b.bits[-1]
        magnitude_a = c.add_subtract(zero,a,negative_a)
        magnitude_b = c.add_subtract(zero,b,negative_b)
        quotient,remainder = c.unsigned_divmod(magnitude_a,magnitude_b)
        quotient = c.add_subtract(zero,quotient,c.XOR(negative_a,negative_b))
        remainder = c.add_subtract(zero,remainder,negative_a)
        # Verilog wraps signed overflow at the expression width. In particular
        # MIN / -1 returns MIN and MIN % -1 returns zero; there is no Wasm trap.
        return quotient,remainder
