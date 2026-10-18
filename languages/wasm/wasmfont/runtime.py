"""Encode inputs, shape once with HarfBuzz, and unpack result bits.

This module deliberately has no dependency on the Wasm evaluator or circuit IR.
Scratch cells are always 'u' (uninitialized). The decoder refuses partial runs.
"""
from __future__ import annotations
import argparse
import ctypes
import hashlib
import json
import re
import time
from pathlib import Path
from fontTools.ttLib import TTFont
from . import harfbuzz as hb


class WasmTrap(RuntimeError): pass
class ExecutionBoundExceeded(RuntimeError): pass
class IncompleteShaping(RuntimeError): pass


class Feature(ctypes.Structure):
    _fields_=[('tag',hb.U),('value',hb.U),('start',hb.U),('end',hb.U)]

shape_full=hb.bind('hb_shape_full',hb.I,[hb.P,hb.P,hb.P,hb.U,hb.P])
set_direction=hb.bind('hb_buffer_set_direction',None,[hb.P,hb.I])
version_string=hb.bind('hb_version_string',ctypes.c_char_p,[])


def register_layout(manifest):
    """Validate the v1 ABI and return its complete glyph order.

    Native circuit tests also use integer widths other than Wasm's i32/i64.
    """
    def invalid():raise ValueError('Invalid or unsupported font ABI manifest')
    def width(typ):
        if not isinstance(typ,str) or not re.fullmatch(r'i[1-9][0-9]{0,4}',typ):invalid()
        bits=int(typ[1:])
        if bits>32766:invalid()
        return bits
    if not isinstance(manifest,dict) or manifest.get('abi')!='wasm-gsub-registers-v1':invalid()
    if any(not isinstance(manifest.get(key),list) for key in ('parameter_types','result_types','results','tape')):invalid()
    if not isinstance(manifest.get('flags'),dict):invalid()
    digest=manifest.get('font_sha256')
    if not isinstance(digest,str) or not re.fullmatch(r'[a-f0-9]{64}',digest):invalid()
    parameters=[width(typ) for typ in manifest['parameter_types']]
    results=[width(typ) for typ in manifest['result_types']]
    if len(manifest['results'])!=len(results) or len(manifest['tape'])>32766:invalid()
    names=['.notdef','space'];wires=set();previous=-1
    for entry in manifest['tape']:
        if not isinstance(entry,dict):invalid()
        wire=entry.get('wire');kind=entry.get('kind')
        if type(wire) is not int or not previous<wire<=9007199254740991:invalid()
        if kind not in ('argument','constant','gate'):invalid()
        previous=wire;wires.add(wire)
        if kind=='argument':
            argument=entry.get('argument');bit=entry.get('bit')
            if type(argument) is not int or not 0<=argument<len(parameters):invalid()
            if type(bit) is not int or not 0<=bit<parameters[argument]:invalid()
        if kind=='constant' and (type(entry.get('constant')) is not int or entry['constant'] not in (0,1)):invalid()
        names.extend((f'w{wire}_0',f'w{wire}_1'))
        if kind=='gate':names.append(f'w{wire}_u')
    if len(names)>=65535:invalid()
    for bits,expected in zip(manifest['results'],results):
        if not isinstance(bits,list) or len(bits)!=expected:invalid()
        if any(type(wire) is not int or wire not in wires for wire in bits):invalid()
    for name,wire in manifest['flags'].items():
        if not isinstance(name,str) or not re.fullmatch(r'(trap|limit)\.[a-z_]+',name):invalid()
        if type(wire) is not int or wire not in wires:invalid()
    return names


class TokenShaper:
    """A cached font face. Use one instance per thread, as a context manager."""
    def __init__(self,font_path,*,expected_order=None):
        self.path=Path(font_path)
        with TTFont(self.path) as font:
            self.order=font.getGlyphOrder()
            cmap=font.getBestCmap() or {}
            self.codepoints={name:cp for cp,name in cmap.items()}
        if expected_order is not None and (self.order!=expected_order or any(
                cmap.get(0xf0000+i)!=name for i,name in enumerate(expected_order[2:]))):
            raise ValueError('font register layout does not match its ABI manifest')
        data=self.path.read_bytes()
        self._storage=ctypes.create_string_buffer(data)
        self.blob=hb.blob_create(self._storage,len(data),0,None,None)
        self.face=hb.face_create(self.blob,0);self.font=hb.font_create(self.face)
        self.closed=False

    def shape(self,tokens,*,enabled=True):
        if self.closed:raise RuntimeError('font shaper is closed')
        buf=hb.buffer_create()
        try:
            hb.set_content(buf,1);set_direction(buf,4) # HB_DIRECTION_LTR
            for i,token in enumerate(tokens):
                if token not in self.codepoints:raise ValueError('unknown glyph token '+token)
                hb.add(buf,self.codepoints[token],i)
            hb.guess(buf)
            feature=Feature(int.from_bytes(b'calt','big'),int(enabled),0,0xffffffff)
            started=time.perf_counter()
            success=shape_full(self.font,buf,ctypes.byref(feature),1,None)
            self.last_harfbuzz_seconds=time.perf_counter()-started
            if not success:
                raise IncompleteShaping('HarfBuzz could not execute this shaping plan')
            count=hb.length(buf)
            infos=ctypes.cast(hb.getinfo(buf,None),ctypes.POINTER(hb.GlyphInfo))
            return [self.order[infos[i].codepoint] for i in range(count)]
        finally:hb.buffer_destroy(buf)

    def close(self):
        if not self.closed:
            hb.font_destroy(self.font);hb.face_destroy(self.face);hb.blob_destroy(self.blob)
            self.closed=True
    def __enter__(self):return self
    def __exit__(self,*args):self.close()


class NativeFont:
    def __init__(self,font_path,manifest_path=None):
        self.path=Path(font_path)
        self.manifest=json.loads(Path(manifest_path or self.path.with_suffix('.json')).read_text())
        order=register_layout(self.manifest)
        if hashlib.sha256(self.path.read_bytes()).hexdigest()!=self.manifest['font_sha256']:
            raise ValueError('font does not match its ABI manifest')
        self.shaper=TokenShaper(font_path,expected_order=order)

    def encode(self,args):
        if len(args)!=len(self.manifest['parameter_types']):raise ValueError('wrong argument count')
        if any(type(x) is not int for x in args):raise TypeError('integer parameters required')
        tokens=[]
        for entry in self.manifest['tape']:
            kind=entry['kind']
            if kind=='argument':value=(args[entry['argument']]>>entry['bit'])&1
            elif kind=='constant':value=entry['constant']
            elif kind=='gate':value='u'
            else:raise ValueError('invalid tape entry')
            tokens.append(f"w{entry['wire']}_{value}")
        return tokens

    def decode(self,tokens):
        tape=self.manifest['tape']
        if len(tokens)!=len(tape):raise IncompleteShaping('shaping changed the tape length')
        values={}
        for entry,token in zip(tape,tokens):
            wire=entry['wire']
            if token not in (f'w{wire}_0',f'w{wire}_1'):
                raise IncompleteShaping(f'wire {wire} is uninitialized or misplaced; no result is valid')
            bit=int(token[-1]);values[wire]=bit
            if entry['kind']=='constant' and bit!=entry['constant']:
                raise IncompleteShaping('corrupted constant cell')
        for name,wire in self.manifest['flags'].items():
            if values[wire]:
                if name.startswith('trap.'):raise WasmTrap(name[5:])
                raise ExecutionBoundExceeded(name[6:])
        return tuple(sum(values[wire]<<bit for bit,wire in enumerate(result))
                     for result in self.manifest['results'])

    def invoke(self,*args):
        result=self.decode(self.shaper.shape(self.encode(args)))
        return result[0] if len(result)==1 else result
    def close(self):self.shaper.close()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('font',type=Path);parser.add_argument('values',nargs='*',type=lambda x:int(x,0))
    args=parser.parse_args()
    try:
        with NativeFont(args.font) as font:print(font.invoke(*args.values))
    except (WasmTrap,ExecutionBoundExceeded,IncompleteShaping,ValueError) as exc:
        parser.exit(2,type(exc).__name__+': '+str(exc)+'\n')

if __name__=='__main__':main()
