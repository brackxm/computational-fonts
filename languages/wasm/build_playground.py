# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Rebuild the bundled static playground fonts, manifests and example catalog."""
import argparse
import json
from pathlib import Path

from wasmfont.frontend import load
from wasmfont.compiler import compile_source
from build_examples import EXAMPLE_LIMITS

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
    ('division_loop64', '64-bit division → typed loop', 'Divide a / b once, then carry the quotient and remainder through a loop: add the remainder to the checksum and increment it each round. Rounds 0–7 finish; 8 reaches the loop bound. A zero divisor traps.', ['dividend', 'divisor', 'rounds'], ['18446744073709551615', '4294967297', '3']),
    ('bulk_memory', 'Memory fill + overlapping copy', 'Store the seed in bytes 0–7, fill bytes 8–15 with the low byte of the fill value, then copy length bytes from source to destination. Overlaps preserve the original source bytes. Both ranges must fit the 16-byte window unless length is zero.', ['seed', 'destination', 'source', 'length', 'fill byte'], ['0x0807060504030201', '2', '0', '8', '0xaa']),
    ('passive_data', 'Passive data → memory', 'Copy bytes from an embedded segment containing 1–16 into the zeroed 16-byte memory window, then drop the segment. Set drop first to 1 to discard it before the copy; only length 0 at source 0 then succeeds.', ['destination', 'segment offset', 'length', 'drop first'], ['0', '4', '8', '0']),
    ('memory_grow', 'Grow memory in the font', 'Start with one page, store the value, then attempt two growth steps up to a maximum of three pages. Each step returns the previous page count or −1 on failure; failed growth preserves the memory size and stored value.', ['first growth (pages)', 'second growth (pages)', 'stored value'], ['1', '2', '0x89abcdef01234567']),
    ('start_memory', 'Initialize before the export', 'A start function grows memory, copies seed bytes 1–16, drops the seed segment, and increments an initialization counter before run changes one byte. Addresses 0–15 fit the backed window. Each run starts with a fresh initialized module.', ['address', 'replacement byte'], ['3', '0xaa']),
    ('indirect64', 'Choose a 64-bit function at runtime', 'Select addition (0), subtraction (1), multiplication (2), or unsigned division (3), then count the result’s set bits. Slot 4 has the wrong signature, slot 5 is null, and indices 6+ are out of bounds. Only the selected function can trap.', ['a', 'b', 'operation index'], ['100', '7', '3']),
    ('mutable_dispatch', 'Change and grow a function table', 'Copy addition and unsigned division from a passive segment, drop the segment, select a function reference, replace slot 0 and grow a new slot with it. Call the new slot and count the result’s bits. Operation 0 adds; 1 divides; other indices trap.', ['a', 'b', 'operation'], ['100', '7', '1']),
    ('reference_flow', 'Pass function references through helpers', 'Choose a nullable table reference or fallback addition, pass it through a helper and typed block, store it in a mutable global, then dispatch and count bits. Slots 0 and 2 add or divide; slot 1 is null. Set use selected slot to 0 for fallback addition; the slot must still be in bounds.', ['a', 'b', 'slot', 'use selected slot'], ['100', '7', '2', '1']),
    ('indexed_memory', 'Indexed byte in a 64-byte window', 'Store an i64 seed at bytes 32–39, then read a byte at a runtime offset and count the seed’s set bits. Offsets 0–63 fit the backed window; higher valid Wasm addresses report a memory bound.', ['byte offset', 'seed'], ['34', '0x0807060504030201']),
    ('divide32', 'Unsigned division', 'Divide two i32 values. A zero divisor produces a Wasm trap.', ['dividend', 'divisor'], ['17', '3']),
    ('divide64_constant', '64-bit division by 10', 'Return the unsigned quotient and remainder of a full-width i64 value divided by ten.', ['value'], ['18446744073709551615']),
    ('divide64_signed', '64-bit signed division by −7', 'Return the signed quotient and remainder. Division truncates toward zero; remainder keeps the input sign.', ['value'], ['-1234567890123456789']),
    ('divide64_dynamic', 'Dynamic 64-bit division', 'Return unsigned quotient and remainder for two full-width i64 arguments. A zero divisor traps.', ['dividend', 'divisor'], ['18446744073709551615', '4294967297']),
    ('divide64_dynamic_signed', 'Dynamic signed 64-bit division', 'Return signed quotient and remainder. Zero divisors and MIN / −1 trap; division truncates toward zero.', ['dividend', 'divisor'], ['-9223372036854775808', '-7']),
    ('multiply64', '64-bit multiplication', 'Multiply arbitrary i64 values with wrapping.', ['a', 'b'], ['0x123456789abcdef0', '7']),
    ('count', 'Count set bits', 'Count the set bits in an i64 integer, then add three.', ['value'], ['0xfedcba9876543210']),
    ('c-mix32', 'Compiled C · i32', 'An exported function from the bundled Clang-produced module.', ['a', 'b'], ['123', '77']),
    ('c-mix64', 'Compiled C · i64', 'The 64-bit export from the same compiled C module.', ['a', 'b'], ['123', '77']),
    ('c-array', 'Compiled C · array loop', 'Add bias to the first count elements of [3, 5, 7, 11], then return their sum with unsigned 32-bit wrapping. Counts 0–4 succeed; other counts trap. The compiled loop reads and writes a 16-byte window at address 65536. Each run starts with the original array.', ['count', 'bias'], ['4', '10']),
    ('c-sparse-array', 'Compiled C · stack and globals', 'Read the first count globals from [3, 5, 7, 11], add bias into a local stack array and sum it in another function. Counts 0–4 succeed. Two 16-byte regions back the stack and globals across a 496-byte gap.', ['count', 'bias'], ['4', '10']),
    ('c-callbacks', 'Compiled C · function pointers', 'Load a volatile C function pointer and pass it to a non-inlined helper. Operation 0 adds, 1 XORs, and 2 divides full-width unsigned i64 inputs. Other operations trap. A zero divisor traps only for operation 2.', ['a', 'b', 'operation'], ['100', '7', '2']),
    ('c-packet', 'Compiled C · packet checksum', 'Copy 0–7 payload bytes from an embedded packet into a local stack buffer, add the adjustment to each byte, then compute a 32-bit rolling checksum in a helper. Counts above the packet header’s limit trap; each invocation starts fresh.', ['payload bytes', 'byte adjustment'], ['7', '10']),
)


def build(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    catalog = []
    for name, title, description, parameters, arguments in EXAMPLES:
        is_c = name.startswith('c-')
        c_source={'c-array':'array','c-sparse-array':'sparse_array','c-callbacks':'callbacks','c-packet':'packet'}.get(name,'mix')
        source = ROOT / 'examples' / (f'{c_source}.wasm' if is_c else f'{name}.wat')
        export = 'run64' if name == 'c-mix64' else 'add' if name == 'add' else 'run'
        limits=EXAMPLE_LIMITS.get(name)
        manifest = compile_source(source, output / f'{name}.ttf', export=export, limits=limits)
        _, data = load(source)
        (output / f'{name}.wasm').write_bytes(data)
        catalog.append({'id': name, 'title': title, 'description': description,
                        'parameters': parameters, 'arguments': arguments,
                        'font': f'{name}.ttf', 'manifest': f'{name}.json', 'module': f'{name}.wasm',
                        'source': (ROOT / 'examples' / f'{c_source}.c' if is_c else source).read_text(),
                        'result_labels': (['Quotient', 'Remainder'] if name.startswith('divide64_') else
                                          ['Checksum', 'Remainder + rounds'] if name == 'division_loop64' else
                                          ['Bytes 0–7 (little endian)', 'Bytes 8–15 (little endian)'] if name in ('bulk_memory','passive_data') else
                                          ['First growth result', 'Second growth result', 'Current pages', 'Preserved value'] if name == 'memory_grow' else
                                          ['Bytes 0–7 (little endian)', 'Bytes 8–15 (little endian)', 'Current pages', 'Initializer calls'] if name == 'start_memory' else
                                          ['Selected result', 'Set bits'] if name in ('indirect64','reference_flow') else
                                          ['Selected result', 'Set bits', 'Current slots'] if name == 'mutable_dispatch' else
                                          ['Selected byte', 'Seed set bits'] if name == 'indexed_memory' else
                                          ['Sum of updated values'] if name in ('c-array','c-sparse-array') else
                                          ['Selected result'] if name == 'c-callbacks' else
                                          ['Rolling checksum'] if name == 'c-packet' else
                                          ['Product', 'Set bits'] if name == 'divmulcount64' else []),
                        'language': 'C' if is_c else 'WAT'})
        print(name, json.dumps(manifest['metrics']))
    (output / 'catalog.json').write_text(json.dumps(catalog, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'playground' / 'assets')
    build(parser.parse_args().output_dir)
