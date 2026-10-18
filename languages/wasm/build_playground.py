# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Rebuild the bundled static playground fonts, manifests and example catalog."""
import argparse
import json
from pathlib import Path

from wasmfont.frontend import load
from wasmfont.compiler import compile_source

ROOT = Path(__file__).resolve().parent
EXAMPLES = (
    ('compose', 'Independent expressions', '(a + b) XOR (a − b), with 32-bit wrapping.', ['a', 'b'], ['123', '77']),
    ('add', 'Wrapping addition', 'Add two i32 integers. Try 4294967295 + 1.', ['a', 'b'], ['4294967295', '1']),
    ('compose64', '64-bit expressions', 'The same expression with full 64-bit integers.', ['a', 'b'], ['0x123456789abcdef0', '0xfedcba9876543210']),
    ('expensive64', 'Two 64-bit dividers + addition', 'Compute (a / b) + (c / d) with independent signed i64 dividers and wrapping addition. Division truncates toward zero; either division can trap.', ['a', 'b', 'c', 'd'], ['-9223372036854775808', '-7', '9223372036854775807', '3']),
    ('divmul64', 'Two 64-bit divisions → multiplication', 'Compute (a / b) × (c / d) with unsigned i64 division and a wrapping product. Both runtime quotients feed the multiplier; either zero divisor traps.', ['a', 'b', 'c', 'd'], ['18446744073709551615', '3', '18446744073709551615', '7']),
    ('divmulcount64', 'Signed divisions → multiply → count bits', 'Return (a / b) × (c / d) and its set-bit count. Four runtime operations compose with signed i64 division and wrapping multiplication. Either zero divisor or MIN / −1 traps.', ['a', 'b', 'c', 'd'], ['-9223372036854775808', '-7', '9223372036854775807', '3']),
    ('three_divs64', 'Three 64-bit dividers + addition', 'Compute (a / b) + (c / d) + (e / f) with three independent unsigned i64 dividers and wrapping addition. Any zero divisor traps.', ['a', 'b', 'c', 'd', 'e', 'f'], ['100', '3', '200', '7', '300', '11']),
    ('four_divs64', 'Four 64-bit dividers + addition', 'Compute (a / b) + (c / d) + (e / f) + (g / h) with four independent unsigned i64 dividers and wrapping addition. Any zero divisor traps.', ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'], ['100', '3', '200', '7', '300', '11', '400', '13']),
    ('branch', 'Conditional branch', 'Return a − b when a < b (signed); otherwise a + b.', ['a', 'b'], ['123', '456']),
    ('sum_loop', 'Bounded loop', 'Sum n down to 1. Inputs 0–7 finish; 8 reaches the loop bound.', ['n'], ['6']),
    ('recursive_sum', 'Recursive calls', 'Sum n down to 1 using internal calls. Inputs 0–7 fit the call bound.', ['n'], ['5']),
    ('memory_roundtrip', 'Memory round trip', 'Store and load a 32-bit value. Addresses 0–12 fit the backed window.', ['address', 'value'], ['3', '0x89abcdef']),
    ('divide32', 'Unsigned division', 'Divide two i32 values. A zero divisor produces a Wasm trap.', ['dividend', 'divisor'], ['17', '3']),
    ('divide64_constant', '64-bit division by 10', 'Return the unsigned quotient and remainder of a full-width i64 value divided by ten.', ['value'], ['18446744073709551615']),
    ('divide64_signed', '64-bit signed division by −7', 'Return the signed quotient and remainder. Division truncates toward zero; remainder keeps the input sign.', ['value'], ['-1234567890123456789']),
    ('divide64_dynamic', 'Dynamic 64-bit division', 'Return unsigned quotient and remainder for two full-width i64 arguments. A zero divisor traps.', ['dividend', 'divisor'], ['18446744073709551615', '4294967297']),
    ('divide64_dynamic_signed', 'Dynamic signed 64-bit division', 'Return signed quotient and remainder. Zero divisors and MIN / −1 trap; division truncates toward zero.', ['dividend', 'divisor'], ['-9223372036854775808', '-7']),
    ('multiply64', '64-bit multiplication', 'Multiply arbitrary i64 values with wrapping.', ['a', 'b'], ['0x123456789abcdef0', '7']),
    ('count', 'Count set bits', 'Count the set bits in an i64 integer, then add three.', ['value'], ['0xfedcba9876543210']),
    ('c-mix32', 'Compiled C · i32', 'An exported function from the bundled Clang-produced module.', ['a', 'b'], ['123', '77']),
    ('c-mix64', 'Compiled C · i64', 'The 64-bit export from the same compiled C module.', ['a', 'b'], ['123', '77']),
)


def build(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    catalog = []
    for name, title, description, parameters, arguments in EXAMPLES:
        is_c = name.startswith('c-mix')
        source = ROOT / 'examples' / ('mix.wasm' if is_c else f'{name}.wat')
        export = 'run64' if name == 'c-mix64' else 'add' if name == 'add' else 'run'
        manifest = compile_source(source, output / f'{name}.ttf', export=export)
        _, data = load(source)
        (output / f'{name}.wasm').write_bytes(data)
        catalog.append({'id': name, 'title': title, 'description': description,
                        'parameters': parameters, 'arguments': arguments,
                        'font': f'{name}.ttf', 'manifest': f'{name}.json', 'module': f'{name}.wasm',
                        'source': (ROOT / 'examples/mix.c' if is_c else source).read_text(),
                        'result_labels': (['Quotient', 'Remainder'] if name.startswith('divide64_') else
                                          ['Product', 'Set bits'] if name == 'divmulcount64' else []),
                        'language': 'C' if is_c else 'WAT'})
        print(name, json.dumps(manifest['metrics']))
    (output / 'catalog.json').write_text(json.dumps(catalog, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'playground' / 'assets')
    build(parser.parse_args().output_dir)
