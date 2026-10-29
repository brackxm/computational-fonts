#!/usr/bin/env python3
# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Compile verified LLVM assembly or bitcode to an executable OpenType font."""
import argparse
from pathlib import Path
from llvmfont import Limits, build


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('-o','--output',type=Path)
    parser.add_argument('--function',help='entry function name')
    parser.add_argument('--optimize',action='store_true',help='run LLVM SROA, instcombine and simplifycfg')
    defaults = Limits()
    for field in vars(defaults):
        parser.add_argument('--'+field.replace('_','-'),type=int,default=getattr(defaults,field))
    args = parser.parse_args()
    output = args.output or args.source.with_suffix('.ttf')
    if output.suffix.lower()!='.ttf': parser.error('output must have a .ttf extension')
    if args.source.resolve() in (output.resolve(),output.with_suffix('.json').resolve()):
        parser.error('font and manifest must not overwrite source')
    try:
        limits = Limits(**{field:getattr(args,field) for field in vars(defaults)})
        manifest = build(args.source,output,function=args.function,limits=limits,optimize=args.optimize)
    except (ValueError,OSError) as error: parser.exit(2,f'LLVM build error: {error}\n')
    print(f"{manifest['function']}: {manifest['metrics']['gates']} gates, {manifest['metrics']['font_bytes']} bytes → {output}")
    print(f'Keep the paired manifest: {output.with_suffix(".json")}')


if __name__=='__main__': main()
