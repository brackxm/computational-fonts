#!/usr/bin/env python3
"""Reproducible size/compile/shaping benchmarks with V8-checked outputs."""
import argparse
import json
import platform
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from importlib.metadata import version
from wasmfont.runtime import NativeFont,version_string
from wasmfont.compiler import compile_source
from wasmfont.frontend import load
from wasmfont.oracle import execute_binary

ROOT=Path(__file__).resolve().parent
CASES=[
 ('compose32','compose.wat','run',(123456789,987654321)),
 ('compose64','compose64.wat','run',(0x123456789abcdef0,0xfedcba9876543210)),
 ('multiply64','multiply64.wat','run',(0x123456789abcdef0,0xfedcba9876543210)),
 ('divide32','divide32.wat','run',(0xfedcba98,0x12345)),
 ('divide64','divide64_dynamic.wat','run',(0xffffffffffffffff,0x100000001)),
 ('divide64-signed','divide64_dynamic_signed.wat','run',(-(1<<63),-7)),
 ('branch','branch.wat','run',(123,456)),
 ('loop','sum_loop.wat','run',(6,)),
 ('recursion','recursive_sum.wat','run',(5,)),
 ('memory','memory_roundtrip.wat','run',(3,0x89abcdef)),
 ('count','count.wat','run',(0xfedcba9876543210,)),
 ('c-mix32','mix.wasm','run',(123456789,987654321)),
 ('c-mix64','mix.wasm','run64',(0x123456789abcdef0,0xfedcba9876543210)),
]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeats',type=int,default=20)
    parser.add_argument('--output',type=Path,default=ROOT/'benchmarks'/'latest.json')
    args=parser.parse_args()
    if args.repeats<3:parser.error('use at least three repetitions')
    report={'environment':{'python':platform.python_version(),'platform':platform.platform(),
                           'fonttools':version('fonttools'),'harfbuzz':version_string().decode(),
                           'node':subprocess.check_output(['node','--version'],text=True).strip()},
            'method':'Fresh builds; cached font face; three warmups; same input per timing run. '
                     'harfbuzz_ms times only hb_shape_full. end_to_end_ms includes input encoding, '
                     'buffer I/O, glyph unpacking and trap checks. V8 runs outside timed sections.',
            'repeats':args.repeats,'benchmarks':[]}
    with tempfile.TemporaryDirectory() as directory:
        for name,file,export,values in CASES:
            source=ROOT/'examples'/file;font=Path(directory)/(name+'.ttf')
            start=time.perf_counter();manifest=compile_source(source,font,export=export)
            compile_ms=(time.perf_counter()-start)*1000
            module,data=load(source);fn=module.functions[module.exports[export][1]]
            expected=execute_binary(data,export,fn.params,[values])[0]
            if 'trap' in expected:raise RuntimeError('benchmark unexpectedly traps')
            expected=tuple(int(v)&((1<<int(t[1:]))-1) for v,t in zip(expected['values'],fn.results))
            hb_times=[];total_times=[]
            with NativeFont(font) as native:
                for _ in range(3):native.invoke(*values)
                for _ in range(args.repeats):
                    start=time.perf_counter();actual=native.invoke(*values)
                    total_times.append((time.perf_counter()-start)*1000)
                    hb_times.append(native.shaper.last_harfbuzz_seconds*1000)
                    actual=(actual,) if len(expected)==1 else actual
                    if actual!=expected:raise AssertionError((name,actual,expected))
            entry={'name':name,'source':file,'export':export,'arguments':[str(v) for v in values],
                   'result':[str(v) for v in expected],**manifest['metrics'],
                   'compile_ms':round(compile_ms,3),'harfbuzz_median_ms':round(statistics.median(hb_times),3),
                   'end_to_end_median_ms':round(statistics.median(total_times),3),
                   'end_to_end_p95_ms':round(sorted(total_times)[max(0,(95*len(total_times)+99)//100-1)],3)}
            report['benchmarks'].append(entry);print(json.dumps(entry),flush=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
