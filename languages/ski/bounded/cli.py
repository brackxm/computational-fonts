"""Run with: python3 languages/ski/run.py 'S (I a) b (I c)'"""
import argparse
import json
import sys
from .runtime import Machine, InputOverflow, MachineError
from .syntax import parse, pretty
from .config import DEFAULT_FONT


def main():
    p=argparse.ArgumentParser(description='Bounded SKI evaluated by one OpenType shaping call')
    p.add_argument('expression')
    p.add_argument('--font',default=DEFAULT_FONT)
    p.add_argument('--fuel',type=int)
    p.add_argument('--encode',action='store_true',help='print the PUA input tape without evaluation')
    p.add_argument('--glyphs',action='store_true',help='include actual output glyph names')
    args=p.parse_args()
    try:
        with Machine(args.font) as machine:
            if args.encode:
                print(machine.encode(args.expression,args.fuel)[0],end='')
                return 0
            r=machine.run(args.expression,args.fuel)
            out={'status':r.status,'prefix':r.expression,'expression':pretty(parse(r.expression)),
                 'steps':r.steps,'shaping_calls':1,'harfbuzz':machine.hb.version,
                 'font_sha256':machine.meta['font_sha256']}
            if args.glyphs:out['glyphs']=r.glyphs
            print(json.dumps(out,indent=2))
            return 0
    except (ValueError, OSError, MachineError) as error:
        kind='input_overflow' if isinstance(error,InputOverflow) else 'error'
        print(json.dumps({'status':kind,'detail':str(error)}),file=sys.stderr)
        return 2

if __name__=='__main__':
    raise SystemExit(main())
