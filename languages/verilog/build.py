#!/usr/bin/env python3
# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Compile one unsigned combinational Verilog module into an OpenType font."""
import argparse
from pathlib import Path

from verilogfont.compiler import build


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('-o', '--output', type=Path, help='TTF destination (default: beside source)')
    parser.add_argument('--max-gates', type=int, default=12000,
                        help='Boolean gate budget, including output copies (default: 12000)')
    args = parser.parse_args()
    output = args.output or args.source.with_suffix('.ttf')
    if output.suffix.lower() != '.ttf':
        parser.error('output must have a .ttf extension')
    if args.source.resolve() in (output.resolve(), output.with_suffix('.json').resolve()):
        parser.error('font and manifest must not overwrite source')
    try:
        manifest = build(args.source.read_text(), output, max_gates=args.max_gates)
    except (ValueError, OSError) as error:
        parser.exit(2, f'Verilog build error: {error}\n')
    print(f"{manifest['module']}: {manifest['metrics']['gates']} gates → {output}")
    print(f'Keep the paired manifest: {output.with_suffix(".json")}')


if __name__ == '__main__':
    main()
