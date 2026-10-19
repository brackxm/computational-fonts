#!/usr/bin/env python3
# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Compile a two-state combinational Verilog design into an OpenType font."""
import argparse
from pathlib import Path

from verilogfont.compiler import build
from verilogfont.syntax import SourceText


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, nargs='+', help='Verilog source files compiled together')
    parser.add_argument('-o', '--output', type=Path, help='TTF destination (default: beside source)')
    parser.add_argument('--top', help='top module (default: the unique module not instantiated elsewhere)')
    parser.add_argument('--max-gates', type=int, default=12000,
                        help='Boolean gate budget, including output copies (default: 12000)')
    parser.add_argument('-P', '--parameter', action='append', default=[], metavar='NAME=VALUE',
                        help='override a module parameter with a decimal integer or sized literal; repeat for multiple parameters')
    args = parser.parse_args()
    output = args.output or args.source[0].with_suffix('.ttf')
    if output.suffix.lower() != '.ttf':
        parser.error('output must have a .ttf extension')
    if any(source.resolve() in (output.resolve(), output.with_suffix('.json').resolve()) for source in args.source):
        parser.error('font and manifest must not overwrite source')
    try:
        parameters = {}
        for item in args.parameter:
            name, separator, value = item.partition('=')
            name = name.strip()
            if not separator or not name or not value.strip():
                raise ValueError('parameter overrides must have the form NAME=VALUE')
            if name in parameters:
                raise ValueError(f'duplicate parameter override: {name}')
            parameters[name] = value.strip()
        manifest = build(SourceText.combine((str(source), source.read_text()) for source in args.source), output, max_gates=args.max_gates, parameters=parameters, top=args.top)
    except (ValueError, OSError) as error:
        parser.exit(2, f'Verilog build error: {error}\n')
    print(f"{manifest['module']}: {manifest['metrics']['gates']} gates → {output}")
    print(f'Keep the paired manifest: {output.with_suffix(".json")}')


if __name__ == '__main__':
    main()
