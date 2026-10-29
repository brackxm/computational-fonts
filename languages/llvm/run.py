#!/usr/bin/env python3
# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Encode integers, shape once in HarfBuzz and decode the LLVM font result."""
import argparse
from pathlib import Path
import llvmfont
from fontcircuit.runtime import NativeFont, WasmTrap, ExecutionBoundExceeded, IncompleteShaping


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('font',type=Path)
    parser.add_argument('values',nargs='*',type=lambda x:int(x,0))
    parser.add_argument('--signed',action='store_true',help='display results as signed two’s-complement integers')
    args = parser.parse_args()
    try:
        with NativeFont(args.font) as font:
            if font.manifest.get('language')!='llvm' or font.manifest.get('llvm_subset')!='bounded-integer-v1':
                raise ValueError('expected an LLVM font/manifest pair')
            values = font.invoke(*args.values)
            if len(font.manifest['results'])==1: values = (values,)
            if args.signed:
                values = tuple(x-(1<<int(t[1:])) if x>>(int(t[1:])-1) else x
                               for x,t in zip(values,font.manifest['result_types']))
            print(' '.join(str(x) for x in values))
    except (ValueError,OSError,WasmTrap,ExecutionBoundExceeded,IncompleteShaping) as error:
        parser.exit(2,f'LLVM run error: {type(error).__name__}: {error}\n')


if __name__=='__main__': main()
