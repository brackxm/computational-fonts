import pytest
from pathlib import Path
from wasmfont.ir import Function, parse_wat, parse_binary, execute
from wasmfont.reference.interpreter import run
from wasmfont.conversions import CONVERSIONS, convert

@pytest.mark.parametrize('op,value,expected',[
 ('i32.wrap_i64',0x100000001,1),('i64.extend_i32_s',0x80000000,0xffffffff80000000),
 ('i64.extend_i32_u',0xffffffff,0xffffffff),('i32.extend8_s',0x80,0xffffff80),
 ('i32.extend16_s',0x8000,0xffff8000),('i64.extend8_s',0xff,0xffffffffffffffff),
 ('i64.extend16_s',0x8000,0xffffffffffff8000),('i64.extend32_s',0x80000000,0xffffffff80000000),
])
def test_conversion(op,value,expected,tmp_path):
    assert convert(op,value)==expected
    source='i64' if op=='i32.wrap_i64' else 'i32' if 'i32_' in op else op[:3]
    result=op[:3]
    f=Function([source],[result],[],[('local.get',0),(op,None)])
    assert execute(f,[value])==[expected]
    assert run([f],0,[value])==[expected]
    wat=tmp_path/'test.wat';wat.write_text(f'(module (func (param {source}) (result {result}) local.get 0 {op}))')
    assert parse_wat(wat)[0].code==f.code
    opcode=next(k for k,v in CONVERSIONS.items() if v==op)
    # Minimal Wasm module with one type and one function.
    def section(k,payload):return bytes([k,len(payload)])+payload
    vt={'i32':0x7f,'i64':0x7e}
    type_section=section(1,bytes([1,0x60,1,vt[source],1,vt[result]]))
    func_section=section(3,bytes([1,0]))
    body=bytes([0,0x20,0,opcode,0x0b]);code_section=section(10,bytes([1,len(body)])+body)
    wasm=tmp_path/'test.wasm';wasm.write_bytes(b'\0asm\1\0\0\0'+type_section+func_section+code_section)
    assert parse_binary(wasm)[0].code==f.code
