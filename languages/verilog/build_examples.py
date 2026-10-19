#!/usr/bin/env python3
# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Rebuild the bundled Verilog fonts and playground catalog reproducibly."""
import json
from pathlib import Path
from verilogfont.compiler import build

HERE = Path(__file__).resolve().parent
EXAMPLES = (
    ('adder', '8-bit adder with carry', 'Nine output bits preserve the carry: try 255 + 1.', [255, 1]),
    ('alu', '8-bit ALU', 'op: 0 add, 1 subtract, 2 XOR, 3 shift left. Compare flags are separate outputs.', [13, 3, 0]),
    ('multiplier', '4 × 4-bit multiplier', 'Two runtime inputs produce the complete eight-bit product.', [13, 11]),
    ('bit_routes', 'Bit routing and reductions', 'Swap nibbles, mask a byte, and compute parity and an AND reduction.', [165, 1]),
    ('signed_math', 'Signed arithmetic and shifts', 'Signed eight-bit inputs produce a full sum and product. Arithmetic right shift preserves the sign.', [-128, 3, 2]),
    ('procedural_alu', 'Combinational always block', 'Blocking assignments and case choose add, subtract, XOR, or packed low nibbles. The ninth bit preserves carry/borrow.', [255, 1, 0]),
    ('hierarchical_adder', 'Two-cell hierarchical adder', 'Two parameterized four-bit adder instances connect through a carry wire and output slices.', [255, 1]),
    ('dynamic_routes', 'Dynamic selects and slice updates', 'Read a bit, read a guarded three-bit window, and patch a slice. Indices above 7 produce a checked read error.', [165, 3, 3]),
    ('population_count', 'Population count with a for loop', 'Eight blocking additions are unrolled at compilation. The output counts the set bits in the input byte.', [165]),
    ('generated_xor', 'Generated XOR lanes', 'Eight generated scopes each instantiate a one-bit XOR cell. Change either byte to run all lanes in the font.', [165, 15]),
    ('array_lookup', 'Function and small array', 'index: 0 selects a, 1 b, 2 a XOR b, 3 NOT a. Indices 4–7 produce a checked array read error.', [165, 15, 2]),
    ('division', 'Signed and unsigned division', 'Compare signed and unsigned quotient/remainder for the same input bits. A zero divisor produces a checked error.', [-23, 5]),
    ('parameter_adder', 'Parameterized adder and mask', 'WIDTH and MASK specialize the font at build time. This font uses WIDTH=8 and MASK=0xA5.', [255, 1]),
)


def main():
    assets = HERE / 'playground/assets'
    assets.mkdir(parents=True, exist_ok=True)
    catalog = []
    for name, title, description, arguments in EXAMPLES:
        source = (HERE / 'examples' / f'{name}.v').read_text()
        manifest = build(source, assets / f'{name}.ttf')
        catalog.append(dict(id=name, title=title, description=description,
                            arguments=[str(n) for n in arguments], font=f'{name}.ttf',
                            manifest=f'{name}.json'))
        print(f"{name}: {manifest['metrics']['gates']} gates")
    (assets / 'catalog.json').write_text(json.dumps(catalog, indent=2) + '\n')


if __name__ == '__main__':
    main()
