"""Real C callbacks and packet loops execute through native font circuits."""
from pathlib import Path
import random
import pytest

from wasmfont.compiler import compile_source,Limits
from wasmfont.frontend import load
from wasmfont.oracle import execute_binary
from wasmfont.runtime import NativeFont,WasmTrap,IncompleteShaping
from wasmfont.reference.interpreter import WasmTrap as ReferenceTrap

ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('name,regions',[
 ('callbacks',((65536,12),)),('packet',((65504,8),(65536,8))),
])
def test_compiled_c_programs_against_v8_reference_and_harfbuzz(tmp_path,name,regions):
    path=ROOT/'examples'/f'{name}.wasm';module,data=load(path)
    fn=module.functions[module.exports['run'][1]]
    assert any(op=='call' for f in module.functions for op,_ in f.code)
    if name=='callbacks':
        assert any(op=='call_indirect' for f in module.functions for op,_ in f.code)
        cases=[(a,b,op) for op in [0,1,2,3,0xffffffff] for a,b in [(100,7),(-1,1),(1,0),(1<<63,-1),(0,0)]]
        rng=random.Random(43)
        cases += [(rng.getrandbits(64),rng.getrandbits(64),rng.randrange(3)) for _ in range(20)]
    else:
        assert sum(op=='loop' for f in module.functions for op,_ in f.code)==2
        cases=[(count,bias) for count in [0,1,3,7,8,0xffffffff] for bias in [0,10,255,256,-1,0x80000000]]
    expected=execute_binary(data,'run',fn.params,cases)
    font=tmp_path/(name+'.ttf');manifest=compile_source(path,font,export='run',limits=Limits(memory_regions=regions))
    assert manifest['metrics']['font_bytes']<2_000_000
    with NativeFont(font) as native:
        for args,want in zip(cases,expected):
            if 'trap' in want:
                with pytest.raises(ReferenceTrap):module.invoke('run',args)
                with pytest.raises(WasmTrap):native.invoke(*args)
            else:
                result=int(want['values'][0])&((1<<int(fn.results[0][1:]))-1)
                assert module.invoke('run',args)==[result]
                assert native.invoke(*args)==result
        good=(100,7,2) if name=='callbacks' else (7,10)
        assert native.invoke(*good)==native.invoke(*good)
        with pytest.raises(IncompleteShaping):native.decode(native.shaper.shape(native.encode(good),enabled=False))
