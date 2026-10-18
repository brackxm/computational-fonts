"""Experimental Wasm -> GSUB compiler: i32.add exported two-argument functions."""
import argparse, re, struct
from pathlib import Path
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString

N=32  # Default width; build() supports 32 and 64

from ..ir import parse_binary, parse_wat, execute

def _check_add(functions):
    if len(functions)!=1: raise NotImplementedError('font backend supports one function')
    f=functions[0]
    if f.locals or len(f.results)!=1 or f.results[0] not in ('i32','i64'):
        raise NotImplementedError('unsupported signature or locals')
    ty=f.results[0]
    if (f.params==[ty,ty] and f.code[:2]==[('local.get',0),('local.get',1)]
        and len(f.code)==3 and f.code[2][0] in (ty+'.'+op for op in ('add','sub','and','or','xor','eq','ne'))):
        return f.code[2][0].split('.')[1]
    for bits in (32,64):
        source_type=f'i{bits}'
        if (f.params==[source_type,source_type] and f.results==['i32']
            and f.code[:2]==[('local.get',0),('local.get',1)]
            and len(f.code)==3 and f.code[2][0] in tuple(source_type+'.'+op for op in ('eq','ne','lt_u','le_u','gt_u','ge_u','lt_s','le_s','gt_s','ge_s'))):
            return f.code[2][0].split('.')[1]
    if (f.params==[ty] and f.code==[('local.get',0),(ty+'.eqz',None)]):
        # eqz produces i32 even for i64; this case is valid only for i32.
        return 'eqz' if ty=='i32' else None
    if (f.params==['i64'] and f.results==['i32'] and
        f.code==[('local.get',0),('i64.eqz',None)]): return 'eqz'
    if len(f.params)==1 and f.params[0] in ('i32','i64') and f.results==[f.params[0]] and f.code==[('local.get',0),(f.params[0]+'.clz',None)]: return 'clz'
    if len(f.params)==1 and f.params[0] in ('i32','i64') and f.results==[f.params[0]] and f.code==[('local.get',0),(f.params[0]+'.ctz',None)]: return 'ctz'
    if len(f.params)==1 and f.params[0] in ('i32','i64') and f.results==[f.params[0]] and f.code==[('local.get',0),(f.params[0]+'.popcnt',None)]: return 'popcnt'
    raise NotImplementedError('GSUB backend supports canonical integer operations only')

def read_wasm(path):return _check_add(parse_binary(path))
def read_wat(path):return _check_add(parse_wat(path))

def build(path, operation="add", width=32, invert_output=False):
    if width not in (32,64): raise ValueError("width must be 32 or 64")
    if operation not in ("add", "and", "or", "xor", "sub", "eqz", "eq", "ne", "lt_u", "le_u", "gt_u", "ge_u", "lt_s", "le_s", "gt_s", "ge_s", "clz", "ctz", "popcnt"):
        raise ValueError("unsupported GSUB operation")
    if not isinstance(invert_output, (bool, int)) or invert_output < 0: raise ValueError("invert_output must be a nonnegative count")
    invert_stages = int(invert_output)
    names=['.notdef','space','c0','c1']+[f'p{a}{b}' for a in range(2) for b in range(2)]+[f'q{a}{b}{c}' for a in range(2) for b in range(2) for c in range(2)]+['s0','s1']+(['t0','t1'] if invert_stages else [])+[f'v{stage}_{bit}' for stage in range(2,invert_stages+1) for bit in (0,1)]
    fb=FontBuilder(1000,isTTF=True);fb.setupGlyphOrder(names)
    glyphs={}
    for name in names:
        pen=TTGlyphPen(None);glyphs[name]=pen.glyph()
    fb.setupGlyf(glyphs);fb.setupHorizontalMetrics({x:(600,0) for x in names})
    fb.setupHorizontalHeader(ascent=800,descent=-200)
    fb.setupCharacterMap({32:'space', **{0xE000+i:name for i,name in enumerate(names) if name not in ('.notdef','space')}})
    fb.setupNameTable({'familyName':'Wasm GSUB Add32','styleName':'Regular','uniqueFontIdentifier':'wasm-gsub-add32','fullName':'Wasm GSUB Add32','psName':'WasmGSUBAdd32'})
    fb.setupOS2(sTypoAscender=800,sTypoDescender=-200,usWinAscent=800,usWinDescent=200)
    fb.setupPost();fb.setupMaxp()
    # Each round consumes one carry+pair, then expands to sum+next carry.
    # This is a 32-stage bit-serial ripple carry, not a 2^64-entry mapping.
    lines=['languagesystem DFLT dflt;','feature calt {']
    for i in range(width):
        lines.append(f'lookup combine{i} {{')
        for c in range(2):
            for a in range(2):
                for b in range(2):
                    lines.append(f'  sub c{c} p{a}{b} by q{a}{b}{c};')
        lines.append(f'}} combine{i};')
        lines.append(f'lookup expand{i} {{')
        for c in range(2):
            for a in range(2):
                for b in range(2):
                    s={'add':a^b^c,'sub':a^b^c,'and':a&b,'or':a|b,'xor':a^b,'eqz':0,'clz':0,'ctz':0,'popcnt':0,'eq':0,'ne':0, **{op:0 for op in ('lt_u','le_u','gt_u','ge_u','lt_s','le_s','gt_s','ge_s')}}[operation]; carry=((a&b)|(a&c)|(b&c)) if operation in ('add','sub') else ((a|c) if operation=='eqz' else ((a^b)|c) if operation in ('eq','ne') else (((1-a)&b) | ((1-(a^b))&c)) if operation in ('lt_u','le_u','gt_u','ge_u','lt_s','le_s','gt_s','ge_s') else 0)
                    if operation in ('gt_u','le_u','gt_s','le_s'):
                        carry=((1-b)&a) | ((1-(a^b))&c)
                    if operation in ('lt_s','le_s','gt_s','ge_s') and i == width-1:
                        aa,bb=(1-b,1-a) if operation in ('gt_s','le_s') else (1-a,1-b)
                        carry=((1-aa)&bb) | ((1-(aa^bb))&c)
                    if operation in ('clz','ctz'):
                        s = (1-a) & (1-c)
                        carry = a | c
                    elif operation == 'popcnt':
                        s = a
                        carry = 0
                    lines.append(f'  sub q{a}{b}{c} by s{s} c{carry};')
        lines.append(f'}} expand{i};')
    for stage in range(1,invert_stages+1):
        src = 's' if stage == 1 else ('t' if stage == 2 else f'v{stage-1}_')
        dst = 't' if stage == 1 else f'v{stage}_'
        lines.append(f'lookup invert_output_{stage} {{ sub {src}0 by {dst}1; sub {src}1 by {dst}0; }} invert_output_{stage};')
    lines.append('} calt;')
    addOpenTypeFeaturesFromString(fb.font,'\n'.join(lines))
    fb.save(str(path))

def encode(a,b,operation="add",width=32):
    if width not in (32,64): raise ValueError("width must be 32 or 64")
    mask=(1<<width)-1
    if operation == "sub": b=(~b)&mask
    if operation in ("eqz", "clz", "ctz", "popcnt"): b=0
    if operation == "clz":
        a = int(f"{a & mask:0{width}b}"[::-1], 2)
    a&=mask;b&=mask
    return ['c1' if operation == 'sub' else 'c0']+[f'p{(a>>i)&1}{(b>>i)&1}' for i in range(width)]

def expected(a,b):return (a+b)&0xffffffff

def main():
    # The original build()/encode() APIs are retained for legacy callers/tests.
    from ..compiler import main as native_main
    native_main()
if __name__=='__main__':main()


def decode_eqz(tokens, width):
    """The final carry is the reduction OR of the input bits."""
    if len(tokens)!=width+1 or tokens[-1] not in ('c0','c1'):
        raise ValueError('invalid shaped eqz output')
    return int(tokens[-1]=='c0')


def decode_comparison(tokens, width, operation):
    """Decode native GSUB reduction accumulator for eq/ne/eqz."""
    if operation not in ('eq', 'ne', 'eqz', 'lt_u', 'le_u', 'gt_u', 'ge_u', 'lt_s', 'le_s', 'gt_s', 'ge_s'):
        raise ValueError('not a comparison')
    if len(tokens) != width + 1 or any(t not in ('s0','s1') for t in tokens[:-1]) or tokens[-1] not in ('c0','c1'):
        raise ValueError('invalid shaped comparison output')
    nonzero = tokens[-1] == 'c1'
    if operation in ('lt_u','lt_s','gt_u','gt_s'): return int(nonzero)
    if operation in ('ge_u','ge_s','le_u','le_s'): return int(not nonzero)
    return int(nonzero if operation == 'ne' else not nonzero)


def decode_count(tokens, width, operation):
    """Decode the unary output of a native GSUB bit-reduction circuit."""
    if operation not in ('clz', 'ctz', 'popcnt'):
        raise ValueError('not a counting operation')
    if len(tokens) != width+1 or any(t not in ('s0','s1') for t in tokens[:-1]) or tokens[-1] not in ('c0','c1'):
        raise ValueError('invalid shaped counting output')
    return tokens[:-1].count('s1')
