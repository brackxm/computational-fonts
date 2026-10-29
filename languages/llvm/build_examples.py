#!/usr/bin/env python3
# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Rebuild demonstration fonts and benchmark actual HarfBuzz shaping."""
import argparse
import json
from pathlib import Path
import platform
import statistics
import time

from llvmlite import binding as llvm
from llvmfont import build, Limits
from fontcircuit.runtime import NativeFont
from fontcircuit import harfbuzz


HERE = Path(__file__).resolve().parent
DEMOS = [
    ('max','max.ll','max',(7,-3),7),
    ('loop','loop.ll','sum',(5,),10),
    ('memory','memory.ll','memory',(3,0xfeedbeef),0xfeedbeef),
    ('clang_max','clang.ll','max',(-5,-2),0xfffffffe),
    ('clang_mix','clang.ll','mix',(0xfffffff0,25),(((0xfffffff0+25)&0xffffffff)^(0xfffffff0>>3))*3&0xffffffff),
    ('clang_indexed','clang.ll','indexed',(2,100),111),
    ('clang_loop','clang.ll','sum_loop',(5,),10),
    ('rust_max','rust.ll','rust_max',(-7,4),4),
    ('rust_mix','rust.ll','rust_mix',(2,3),((2+3)<<7)^3),
    ('clang_lookup','clang-intrinsics.ll','constant_lookup',(2,),7),
    ('clang_copied','clang-intrinsics.ll','copied_array',(2,100),110),
    ('clang_checked_add','clang-intrinsics.ll','checked_add',(0xffffffff,1),1<<32),
    ('clang_checked_mul','clang-intrinsics.ll','checked_multiply',(0x7fffffff,2),0x1fffffffe),
    ('rust_lookup','rust-intrinsics.ll','rust_lookup',(2,),7),
    ('rust_checked_add','rust-intrinsics.ll','rust_checked_add',(0xffffffff,1),1<<32),
    ('rust_checked_mul','rust-intrinsics.ll','rust_checked_multiply',(0x7fffffff,2),0x1fffffffe),
    ('clang_sat_add','clang-state.ll','saturating_add',(0xffffffff,1),0xffffffff),
    ('clang_sat_sub','clang-state.ll','saturating_sub',(-2147483648,1),0x80000000),
    ('clang_global_calls','clang-state.ll','global_calls',(1,100),108),
    ('clang_pointer_table','clang-state.ll','pointer_table',(1,100),111),
    ('clang_pointer_copy','clang-state.ll','pointer_copy',(1,100),101),
    ('rust_sat_add','rust-state.ll','rust_saturating_add',(0xffffffff,1),0xffffffff),
    ('rust_sat_sub','rust-state.ll','rust_saturating_sub',(-2147483648,1),0x80000000),
    ('rust_global_calls','rust-state.ll','rust_global_calls',(1,100),108),
    ('rust_pointer_table','rust-state.ll','rust_pointer_table',(1,100),111),
    ('rust_pointer_copy','rust-state.ll','rust_pointer_copy',(1,100),101),
    ('clang_dispatch','clang-dispatch.ll','dispatch',(2,10,3),31),
    ('clang_dispatch_twice','clang-dispatch.ll','dispatch_twice',(3,10,3),14),
    ('clang_copied_dispatch','clang-dispatch.ll','copied_dispatch',(1,10,3),29),
    ('clang_ctor_callback','clang-dispatch.ll','constructor_dispatch',(10,3),31),
    ('clang_constructors','clang-constructors.ll','initialized',(5,),27),
    ('rust_dispatch','rust-dispatch.ll','rust_dispatch',(2,10,3),31),
    ('rust_dispatch_twice','rust-dispatch.ll','rust_dispatch_twice',(3,10,3),14),
    ('rust_copied_dispatch','rust-dispatch.ll','rust_copied_dispatch',(1,10,3),29),
    ('rust_ctor_callback','rust-dispatch.ll','rust_constructor_dispatch',(10,3),31),
    ('alias_table','aliases.ll','alias_table',(1,50),37),
    ('rust_aliases','rust-aliases.ll','alias_dispatch',(1,0xffffffff),6),
    ('rust_merged_aliases','rust-merged-aliases.ll','alias_dispatch',(0,35),42),
    ('rust_alias_entry','rust-merged-aliases.ll','original',(35,),42),
    ('clang_triple','clang-abi.ll','make_triple',(10,3),(13,9,7)),
    ('clang_triple_callback','clang-abi.ll','choose_triple',(1,10,3),(13,9,(1<<64)-7)),
    ('clang_triple_calls','clang-abi.ll','call_triple',(10,3),26),
    ('clang_byval','clang-byval.ll','use_triple',(13,9,7),26),
    ('clang_byval_calls','clang-byval.ll','call_triple',(10,3),26),
    ('rust_triple','rust-abi.ll','rust_triple',(10,3),tuple(b for n in (13,9,7) for b in n.to_bytes(8,'little'))),
    ('rust_triple_calls','rust-abi.ll','rust_call_triple',(10,3),26),
    ('rust_triple_callback','rust-abi.ll','rust_choose_triple',(1,10,3),tuple(b for n in (13,9,(1<<64)-7) for b in n.to_bytes(8,'little'))),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iterations',type=int,default=20)
    args = parser.parse_args()
    if args.iterations<1: parser.error('iterations must be positive')
    reports = []
    for name,source,function,inputs,expected in DEMOS:
        output = HERE/'fonts'/f'{name}.ttf'
        manifest = build(HERE/'examples'/source,output,function=function,limits=Limits(max_steps=32))
        compile_seconds = build.last_seconds
        with NativeFont(output) as machine:
            assert machine.invoke(*inputs)==expected,(name,inputs)
            for _ in range(2): machine.invoke(*inputs)
            total_times,hb_times = [],[]
            for _ in range(args.iterations):
                started = time.perf_counter()
                assert machine.invoke(*inputs)==expected
                total_times.append(time.perf_counter()-started)
                hb_times.append(machine.shaper.last_harfbuzz_seconds)
            if name=='max':
                before = machine.encode(inputs)
                after = machine.shaper.shape(before)
                (HERE/'benchmarks/max-trace.json').write_text(json.dumps({
                    'arguments':inputs,'before':before,'after':after,
                    'result':machine.decode(after),'font_sha256':manifest['font_sha256'],
                },indent=2)+'\n')
        report = dict(name=name,source=source,function=function,inputs=inputs,result=expected,
                      compile_seconds=compile_seconds,
                      harfbuzz_median_seconds=statistics.median(hb_times),
                      invoke_median_seconds=statistics.median(total_times),
                      iterations=args.iterations,metrics=manifest['metrics'])
        reports.append(report)
        print(f"{name}: {report['metrics']['gates']} gates, {report['metrics']['font_bytes']} bytes, "
              f"{compile_seconds:.3f}s build, {statistics.median(hb_times)*1000:.3f}ms shaping")
    import ctypes
    harfbuzz.hb.hb_version_string.restype = ctypes.c_char_p
    (HERE/'benchmarks/latest.json').write_text(json.dumps({
        'platform':platform.platform(),'python':platform.python_version(),
        'llvm_version':list(llvm.llvm_version_info),
        'harfbuzz_version':harfbuzz.hb.hb_version_string().decode(),
        'benchmarks':reports,
    },indent=2)+'\n')


if __name__=='__main__': main()
