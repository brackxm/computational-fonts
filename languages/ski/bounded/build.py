"""Compile a finite, normal-order SKI tree machine into OpenType GSUB."""
from __future__ import annotations
import argparse
import copy
import json
import time
import hashlib
import fontTools
from pathlib import Path
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString

from .layout import VALUES, paths, validate
from .config import DEFAULT_FONT
from .outputs import validate_machine_output

def build(out, depth=5, rounds=32):
    validate(depth, rounds)
    validate_machine_output(out)
    started=time.perf_counter()
    ps=paths(depth); ix={p:i for i,p in enumerate(ps)}; n=len(ps)
    redexes=[(op,p) for p in ps for op,arity in [('I',1),('K',2),('S',3)] if len(p)+arity<=depth]
    modes=[f'run{op}{ix[p]}' for op,p in redexes]
    bases=['seek','normal','budget','overflow']+modes+[f'f{i}' for i in range(rounds+1)]
    main=[f'n{j}_{v}' for j in range(n) for v in VALUES]
    aux=[f'b{j}_{v}' for j in range(n) for v in VALUES]
    tags=[f't{j}' for j in range(n)]
    blanks=[f'q{j}' for j in range(n)]
    pointers=[f'p{j}' for j in range(n)]
    raw=[f'v{v}' for v in VALUES]
    marks=main+aux+tags+blanks+pointers+raw
    glyphs=['.notdef']+bases+marks
    chars=['seek']+[f'f{i}' for i in range(rounds+1)]+main+tags+blanks
    cmap={0xE000+i:g for i,g in enumerate(chars)}
    if max(cmap)>0xF8FF: raise ValueError('input cmap exceeds BMP private use range')
    fb=FontBuilder(1000,isTTF=True);fb.setupGlyphOrder(glyphs);fb.setupCharacterMap(cmap)
    empty=TTGlyphPen(None).glyph()
    fb.setupGlyf({g:empty for g in glyphs});fb.setupHorizontalMetrics({g:(0,0) for g in glyphs})
    fb.setupHorizontalHeader(ascent=800,descent=-200)
    fb.setupNameTable({
        'familyName':'SKI Bounded Tree', 'styleName':'Regular',
        'uniqueFontIdentifier':f'SKI-Bounded-{depth}-{rounds}',
        'fullName':f'SKI Bounded Tree D{depth} B{rounds}',
        'psName':f'SKIBounded-D{depth}-B{rounds}',
        'copyright':'Copyright 2026 Michael Brackx',
        'manufacturer':'computational-fonts',
        'description':'Bounded SKI evaluator using OpenType GSUB. Empty outlines; PUA machine input.',
        'licenseDescription':'Licensed under the Apache License, Version 2.0.',
        'licenseInfoURL':'https://www.apache.org/licenses/LICENSE-2.0',
    })
    fb.setupOS2(sTypoAscender=800,sTypoDescender=-200,usWinAscent=800,usWinDescent=200)
    fb.setupPost();fb.setupMaxp()
    lines=['languagesystem DFLT dflt;']
    def cls(name, gs): lines.append('@'+name+' = ['+' '.join(gs)+'];')
    cls('BASE',bases);cls('MARK',marks);cls('RUN',modes);cls('Q',blanks);cls('P',pointers);cls('RAW',raw)
    for j in range(n):
        cls(f'N{j}',[f'n{j}_{v}' for v in VALUES])
        cls(f'READ{j}',[f'n{j}_{v}' for v in VALUES]+[f'p{j}'])
        cls(f'WRITE{j}',[f'n{j}_{v}' for v in VALUES]+[f'b{j}_{v}' for v in VALUES])
    lines+=['table GDEF { GlyphClassDef @BASE, , @MARK, ; } GDEF;']
    schedule=[]
    def lookup(name, body, flag='', scheduled=True):
        lines.append(f'lookup {name} useExtension {{')
        if flag:lines.append('lookupflag '+flag+';')
        lines.extend(body);lines.append(f'}} {name};')
        if scheduled:schedule.append(name)
    def context_to(j):return ' '.join(f'@N{k}' for k in range(j))
    selection=[]
    for op,p in redexes:
        j=ix[p]; arity={'I':1,'K':2,'S':3}[op]
        chain=' '.join([f'n{ix[p+"0"*k]}_A' for k in range(arity)]+[f'n{ix[p+"0"*arity]}_{op}'])
        selection.append(f"sub seek' {context_to(j)} {chain} by run{op}{j};")
    # A fallback single substitution cannot be mixed with contextual rules.
    selection.append("sub seek' by normal;")
    lookup('select',selection)
    lookup('fuelcheck',["sub @RUN' f0 by budget;"], 'IgnoreMarks')
    guard=[]
    for op,p in redexes:
        if op!='S':continue
        for s in ps:
            if s.startswith(p+'1') and len(s)==depth:
                j=ix[s]; occupied='['+' '.join(f'n{j}_{v}' for v in VALUES if v!='E')+']'
                guard.append(f"sub runS{ix[p]}' {context_to(j)} {occupied} by overflow;")
    if guard:lookup('depthcheck',guard)
    dispatch=[]
    for op,p in redexes:
        body=[]
        for j,dest in enumerate(ps):
            src=dest;const=None
            if dest.startswith(p):
                rel=dest[len(p):]
                if op=='I':src=p+'1'+rel
                elif op=='K':src=p+'01'+rel
                elif rel in ('','0','1'):const='A'
                else:
                    region=rel[:2]
                    origin={'00':'001','01':'1','10':'01','11':'1'}[region]
                    src=p+origin+rel[2:]
            target=f'v{const}' if const else (f'p{ix[src]}' if src in ix else 'vE')
            body.append(f'sub q{j} by {target};')
        name=f'map{op}{ix[p]}'
        lookup(name,body,scheduled=False)
        dispatch.append(f"sub run{op}{ix[p]} @Q' lookup {name};")
    lookup('dispatch',dispatch,'UseMarkFilteringSet @Q')
    for v in VALUES:
        lookup(f'raw{v}',[f'sub @P by v{v};'],scheduled=False)
        lookup(f'put{v}',[f'sub @N{j} by n{j}_{v};' for j in range(n)],scheduled=False)
    for j in range(n):
        lookup(f'read{j}',[f"sub n{j}_{v} p{j}' lookup raw{v};" for v in VALUES],f'UseMarkFilteringSet @READ{j}')
        lookup(f'addr{j}',[f'sub v{v} by b{j}_{v};' for v in VALUES],scheduled=False)
    lookup('address',[f"sub t{j} @RAW' lookup addr{j};" for j in range(n)])
    for j in range(n):
        lookup(f'write{j}',[f"sub @N{j}' lookup put{v} b{j}_{v};" for v in VALUES],f'UseMarkFilteringSet @WRITE{j}')
    lookup('tick',[f"sub @RUN f{i}' by f{i-1};" for i in range(1,rounds+1)],'IgnoreMarks') if rounds else None
    lookup('reset',[f'sub b{j}_{v} by q{j};' for j in range(n) for v in VALUES]+[f'sub {mode} by seek;' for mode in modes])
    # Compile once. Repeated references inside one feature are de-duplicated by
    # shaping; allocate distinct LookupList indices for each finite round below.
    lines+=['feature calt {']+['lookup '+name+';' for name in schedule]+['} calt;']
    fea='\n'.join(lines)
    addOpenTypeFeaturesFromString(fb.font,fea)
    gs=fb.font['GSUB'].table
    feature=next(r.Feature for r in gs.FeatureList.FeatureRecord if r.FeatureTag=='calt')
    cycle=list(feature.LookupListIndex)
    # The first two scheduled lookups select a redex and check remaining fuel.
    final=cycle[:2]
    active=[]
    for indices in [cycle]*rounds+[final]:
        for index in indices:
            active.append(len(gs.LookupList.Lookup))
            gs.LookupList.Lookup.append(copy.copy(gs.LookupList.Lookup[index]))
    gs.LookupList.LookupCount=len(gs.LookupList.Lookup)
    feature.LookupListIndex=active;feature.LookupCount=len(active)
    fb.font['head'].created=fb.font['head'].modified=2082844800
    fb.font.recalcTimestamp=False
    out=Path(out);out.parent.mkdir(parents=True,exist_ok=True);fb.font.save(out)
    meta={'depth':depth,'rounds':rounds,'capacity':n,'glyphs':len(glyphs),'lookups':len(gs.LookupList.Lookup),'active_lookups':len(active),'cycle_lookups':len(cycle),'font_bytes':out.stat().st_size,'schema':1,'tape_glyphs':3*n+2,'redex_locations':len(redexes),'fonttools':fontTools.__version__,'font_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'fea_bytes':len(fea),'chars':{v:k for k,v in cmap.items()}}
    out.with_suffix('.json').write_text(json.dumps(meta,indent=2)+'\n')
    out.with_suffix('.fea').write_text(fea)
    timing={'build_seconds':time.perf_counter()-started}
    out.with_suffix('.build.json').write_text(json.dumps(timing,indent=2)+'\n')
    print({k:v for k,v in meta.items() if k!='chars'} | timing,flush=True)
    return meta

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--depth',type=int,default=5)
    parser.add_argument('--rounds',type=int,default=32)
    parser.add_argument('--output','--out',type=Path,default=DEFAULT_FONT)
    args=parser.parse_args()
    try:
        build(args.output,args.depth,args.rounds)
    except ValueError as error:
        parser.error(str(error))


if __name__=='__main__':
    main()
