#!/usr/bin/env python3
# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Encode port values, shape the font once, and print named unsigned outputs."""
import argparse
from pathlib import Path
import re
import verilogfont  # exposes the shared register runtime
from fontcircuit.runtime import NativeFont, IncompleteShaping


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('font', type=Path)
    parser.add_argument('values', nargs='*', type=lambda x: int(x, 0),
                        help='input values in declaration order; decimal, 0x or 0b')
    args = parser.parse_args()
    try:
        with NativeFont(args.font) as font:
            manifest = font.manifest
            if manifest.get('language') != 'verilog' or manifest.get('verilog_subset') != 'unsigned-combinational-v1':
                raise ValueError('expected a Verilog font/manifest pair')
            for ports, types in ((manifest.get('inputs'), manifest['parameter_types']),
                                 (manifest.get('outputs'), manifest['result_types'])):
                if (not isinstance(ports, list) or len(ports) != len(types) or
                    any(not isinstance(port, dict) or
                        not isinstance(port.get('name'), str) or
                        not re.fullmatch(r'[a-zA-Z_][a-zA-Z_0-9$]*', port['name']) or
                        type(port.get('width')) is not int or
                        not 1 <= port['width'] <= 64 or types[i] != f"i{port['width']}"
                        for i, port in enumerate(ports))):
                    raise ValueError('invalid Verilog port metadata')
            result = font.invoke(*args.values)
            values = (result,) if len(manifest['outputs']) == 1 else result
            for port, value in zip(manifest['outputs'], values):
                print(f"{port['name']}={value} (0x{value:0{(port['width']+3)//4}x}, {port['width']}'b{value:0{port['width']}b})")
    except (ValueError, OSError, IncompleteShaping) as error:
        parser.exit(2, f'Verilog run error: {error}\n')


if __name__ == '__main__':
    main()
