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
