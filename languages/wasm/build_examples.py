#!/usr/bin/env python3
"""Build every demonstration locally, including the supplied C-produced Wasm."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
from wasmfont.compiler import compile_source, Limits

ROOT=Path(__file__).resolve().parent
EXAMPLE_LIMITS={
    'c-array':Limits(memory_base=65536),
    'c-sparse-array':Limits(memory_regions=((65024,16),(65536,16))),
    'indexed_memory':Limits(memory_bytes=64),
    'indexed_words':Limits(memory_bytes=64,max_gates=8000),
    'c-callbacks':Limits(memory_regions=((65536,12),)),
    'c-packet':Limits(memory_regions=((65504,8),(65536,8))),
    'tail_calls':Limits(call_depth=1),
    'tail_reference64':Limits(call_depth=1),
    'typed_dispatch':Limits(call_depth=1),
    'c-tail-callbacks':Limits(call_depth=1,memory_regions=((65536,12),)),
}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'examples'/'generated')
    parser.add_argument('--recompile-c',action='store_true')
    args=parser.parse_args();args.output_dir.mkdir(parents=True,exist_ok=True)
    if args.recompile_c:
        clang=shutil.which('clang')
        if not clang:parser.error('Clang with wasm32 target support is required')
        subprocess.run([clang,'--target=wasm32','-O2','-nostdlib','-ffreestanding','-Wl,--no-entry',
                        '-Wl,--export=run','-Wl,--export=run64','-Wl,--strip-all',str(ROOT/'examples'/'mix.c'),
                        '-o',str(ROOT/'examples'/'mix.wasm')],check=True)
        for name in ('array','sparse_array','callbacks','packet'):
            subprocess.run([clang,'--target=wasm32','-O2','-fno-unroll-loops','-nostdlib','-ffreestanding',
                            '-Wl,--no-entry','-Wl,--export=run','-Wl,--strip-all',
                            '-Wl,--stack-first','-Wl,-z,stack-size=65536',str(ROOT/'examples'/(name+'.c')),
                            '-o',str(ROOT/'examples'/(name+'.wasm'))],check=True)
        subprocess.run([clang,'--target=wasm32','-O2','-fno-unroll-loops','-mtail-call','-nostdlib','-ffreestanding',
                        '-Wl,--no-entry','-Wl,--export=run','-Wl,--strip-all','-Wl,--stack-first',
                        '-Wl,-z,stack-size=65536',str(ROOT/'examples'/'callbacks.c'),
                        '-o',str(ROOT/'examples'/'callbacks_tail.wasm')],check=True)
    builds=[(p,p.stem,None) for p in sorted((ROOT/'examples').glob('*.wat'))]
    builds += [(ROOT/'examples'/'mix.wasm','c-mix32','run'),(ROOT/'examples'/'mix.wasm','c-mix64','run64')]
    builds += [(ROOT/'examples'/(name+'.wasm'),'c-'+name.replace('_','-'),'run')
               for name in ('array','sparse_array','callbacks','packet')]
    builds.append((ROOT/'examples'/'callbacks_tail.wasm','c-tail-callbacks','run'))
    report={}
    for source,name,export in builds:
        limits=EXAMPLE_LIMITS.get(name)
        manifest=compile_source(source,args.output_dir/(name+'.ttf'),export=export,limits=limits)
        report[name]=manifest['metrics']
        print(name,json.dumps(manifest['metrics']))
    (args.output_dir/'build-report.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
