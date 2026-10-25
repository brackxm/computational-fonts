# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Packed blocks retain every rule and shape identically across offset windows."""
from io import StringIO
from itertools import product
from copy import deepcopy
from pathlib import Path
import sys

import pytest
from fontTools.misc.xmlWriter import XMLWriter
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.otBase import OTTableReader
from fontTools.ttLib.tables.otTables import ChainContextSubst

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fontcircuit.gsub import tables
from fontcircuit.gsub.circuit import Circuit, Value, emit_font
from fontcircuit.runtime import IncompleteShaping, NativeFont


def xml(table, font):
    output=StringIO()
    table.toXML(XMLWriter(output), font)
    return output.getvalue()


def decode_subtable(data, start, font):
    table=ChainContextSubst()
    table.decompile(OTTableReader(data, offset=start), font)
    return xml(table, font)


@pytest.mark.parametrize('copies', [1, 4000])
def test_shared_blocks_preserve_both_formats_across_offset_windows(copies):
    circuit=Circuit()
    a,b=circuit.argument(0,2).bits
    destination=circuit.XOR(a,b)
    names=['.notdef']+[f'w{wire}_{value}' for wire in (a,b,destination) for value in (0,1,'u')]
    gids={name:i for i,name in enumerate(names)}
    sources=[tables.gate_subtable([destination],circuit,gids),
             tables.batched_gate_subtable([destination],circuit,gids,[a,b,destination])]
    font=TTFont();font.setGlyphOrder(names)
    expected=[decode_subtable(source,0,font) for source in sources]
    payloads=sources*copies
    packed,positions=tables.pack_chained_subtables(payloads)
    assert len(positions)==len(payloads)
    assert positions==sorted(set(positions))
    assert len(packed)<sum(map(len,payloads))
    if copies>1:
        original,_=tables._pack_chained_windows(payloads,by_unique=False)
        assert len(packed)<len(original)
        assert positions[-1]>65535
    for i,start in enumerate(positions):
        assert decode_subtable(packed,start,font)==expected[i%2]


@pytest.mark.parametrize('batch_size,coalesce', [(1,False), (64,False), (64,True)])
def test_smaller_fonts_preserve_complete_gsub_and_native_results(tmp_path,monkeypatch,batch_size,coalesce):
    circuit=Circuit()
    arguments=[circuit.argument(i,4) for i in range(12)]
    results=[circuit.add(argument,circuit.const(3,4)) for argument in arguments]
    packed=tmp_path/'packed.ttf';original=tmp_path/'original.ttf'
    options=dict(lookup_batch_size=batch_size,lookup_coalescing=coalesce)
    # Hold the representation fixed while comparing block storage. Without
    # sharing, the automatic choice may legitimately prefer Format 1 instead.
    attach=tables._attach_layout
    def class_layout(*args,**kwargs):
        kwargs['class_singletons']=True
        return attach(*args,**kwargs)
    monkeypatch.setattr(tables,'_attach_layout',class_layout)
    packed_manifest=emit_font(deepcopy(circuit),results,{},['i4']*12,['i4']*12,packed,**options)
    # The reference layout stores each original subtable consecutively.
    with monkeypatch.context() as patch:
        patch.setattr(tables,'pack_chained_subtables',
                      lambda items: unpacked(list(items)))
        original_manifest=emit_font(circuit,results,{},['i4']*12,['i4']*12,original,**options)
    assert packed.stat().st_size<=original.stat().st_size
    assert packed.stat().st_size<original.stat().st_size
    for key in ('abi','tape','results','flags','parameter_types','result_types'):
        assert packed_manifest[key]==original_manifest[key]
    with TTFont(packed) as new,TTFont(original) as old:
        assert new.getGlyphOrder()==old.getGlyphOrder()
        assert xml(new['GSUB'].table,new)==xml(old['GSUB'].table,old)
        assert xml(new['GDEF'].table,new)==xml(old['GDEF'].table,old)
    with NativeFont(packed) as new,NativeFont(original) as old:
        for value in range(16):
            inputs=tuple((value+i)&15 for i in range(12))
            expected=tuple((argument+3)&15 for argument in inputs)
            assert new.invoke(*inputs)==old.invoke(*inputs)==expected
        with pytest.raises(IncompleteShaping):
            new.decode(new.shaper.shape(new.encode(inputs),enabled=False))


def unpacked(items):
    return b''.join(items),tables.block_offsets(items,0)


def test_write_lookups_share_one_complete_scratch_coverage(tmp_path):
    import struct
    circuit=Circuit()
    value=circuit.argument(0,4)
    result=circuit.add(value,circuit.const(3,4))
    path=tmp_path/'writes.ttf'
    emit_font(circuit,[result],{},['i4'],['i4'],path)
    with TTFont(path) as font:
        raw=font.getTableData('GSUB')
        lookup_list=struct.unpack_from('>H',raw,8)[0]
        coverage_addresses=[]
        for index,delta in enumerate((-2,-1)):
            lookup=lookup_list+struct.unpack_from('>H',raw,lookup_list+2+2*index)[0]
            assert struct.unpack_from('>H',raw,lookup)[0]==7
            extension=lookup+struct.unpack_from('>H',raw,lookup+6)[0]
            subtable=extension+struct.unpack_from('>I',raw,extension+4)[0]
            format,offset,actual_delta=struct.unpack_from('>HHh',raw,subtable)
            assert (format,actual_delta)==(1,delta)
            coverage_addresses.append(subtable+offset)
        assert coverage_addresses[0]==coverage_addresses[1]
        address=coverage_addresses[0]
        format,count=struct.unpack_from('>HH',raw,address)
        assert format==1
        scratch=struct.unpack_from('>'+str(count)+'H',raw,address+4)
        expected=[gid for gid,name in enumerate(font.getGlyphOrder()) if name.endswith('_u')]
        assert list(scratch)==expected
        for gid in scratch:
            assert font.getGlyphName(gid-2)==font.getGlyphName(gid)[:-1]+'0'
            assert font.getGlyphName(gid-1)==font.getGlyphName(gid)[:-1]+'1'


def test_automatic_policy_keeps_the_smaller_valid_layout(tmp_path):
    circuit=Circuit()
    a=circuit.argument(0,4)
    b=circuit.argument(1,4)
    outputs=circuit.unsigned_divmod(a,b)
    fonts={}
    for policy in (False,True,None):
        path=tmp_path/f'{policy}.ttf'
        emit_font(deepcopy(circuit),outputs,{},['i4','i4'],['i4','i4'],path,
                  lookup_batch_size=8,lookup_coalescing=policy)
        fonts[policy]=path
    assert fonts[None].stat().st_size==min(fonts[p].stat().st_size for p in (False,True))
    with NativeFont(fonts[None]) as font:
        for dividend in range(16):
            for divisor in range(1,16):
                assert font.invoke(dividend,divisor)==divmod(dividend,divisor)


@pytest.mark.parametrize('mapping,format', [
    ({10:2,11:3,12:1,13:4},1), ({1:2,500:3,999:1},2),
    ({},2), ({gid:2 for gid in range(10,30)},2),
])
def test_class_definition_chooses_smaller_encoding_with_identical_default_zero(mapping,format):
    from fontTools.ttLib.tables.otTables import ClassDef
    data=tables.class_definition(mapping)
    assert int.from_bytes(data[:2],'big')==format
    font=TTFont();font.setGlyphOrder([f'g{i}' for i in range(1001)])
    table=ClassDef();table.decompile(OTTableReader(data),font)
    assert [table.classDefs.get(f'g{i}',0) for i in range(1001)]==[mapping.get(i,0) for i in range(1001)]


def test_singleton_class_rules_preserve_native_results_and_choose_smaller_storage(tmp_path,monkeypatch):
    circuit=Circuit()
    a,b=circuit.argument(0,4),circuit.argument(1,4)
    results=circuit.unsigned_divmod(a,b)
    attach=tables._attach_layout
    paths={}
    manifests={}
    for mode in (False,True,None):
        path=tmp_path/f'{mode}.ttf'
        with monkeypatch.context() as patch:
            if mode is not None:
                def layout(*args,**kwargs):
                    kwargs['class_singletons']=mode
                    return attach(*args,**kwargs)
                patch.setattr(tables,'_attach_layout',layout)
            manifests[mode]=emit_font(deepcopy(circuit),results,{},['i4','i4'],['i4','i4'],path,
                                      lookup_batch_size=1,lookup_coalescing=False)
        paths[mode]=path
    assert paths[True].stat().st_size<paths[False].stat().st_size
    assert paths[None].read_bytes()==paths[True].read_bytes()
    assert manifests[True]['metrics']['class_singleton_groups']>0
    for key in ('abi','tape','results','flags','parameter_types','result_types'):
        assert manifests[False][key]==manifests[True][key]==manifests[None][key]
    for path in paths.values():
        with NativeFont(path) as font:
            for dividend in range(16):
                for divisor in range(1,16):
                    assert font.invoke(dividend,divisor)==divmod(dividend,divisor)


def test_uninitialized_operand_never_matches_the_sparse_wildcard_class(tmp_path,monkeypatch):
    import hashlib,json
    circuit=Circuit()
    a,b,c=[circuit.argument(i,1).bits[0] for i in range(3)]
    intermediate=circuit.XOR(a,b)
    output=circuit.AND(intermediate,c)
    path=tmp_path/'missing-producer.ttf'
    attach=tables._attach_layout
    def layout(*args,**kwargs):
        kwargs['class_singletons']=True
        return attach(*args,**kwargs)
    monkeypatch.setattr(tables,'_attach_layout',layout)
    manifest=emit_font(circuit,[Value((output,))],{},['i1']*3,['i1'],path,
                       lookup_batch_size=1,lookup_coalescing=False)
    with TTFont(path) as font:
        gsub=font['GSUB'].table
        feature=gsub.FeatureList.FeatureRecord[0].Feature
        # Remove only the producer. Its dependent operands remain uninitialized
        # even though the rest of the computation still runs.
        feature.LookupListIndex=feature.LookupListIndex[1:]
        feature.LookupCount=len(feature.LookupListIndex)
        for lookup in gsub.LookupList.Lookup[3:]:
            for extension in lookup.SubTable:
                subtable=extension.ExtSubTable
                assert subtable.Format==2
                if f'w{intermediate}_u' in subtable.BacktrackClassDef.classDefs:
                    assert subtable.BacktrackClassDef.classDefs[f'w{intermediate}_u']==1
                    assert subtable.BacktrackClassDef.classDefs[f'w{intermediate}_0']>=2
        font.recalcTimestamp=False;font.save(path)
    manifest['font_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    manifest['metrics']['font_bytes']=path.stat().st_size
    path.with_suffix('.json').write_text(json.dumps(manifest))
    with NativeFont(path) as font:
        for args in product((0,1),repeat=3):
            tokens=font.shaper.shape(font.encode(args))
            assert f'w{output}_u' in tokens
            with pytest.raises(IncompleteShaping):font.decode(tokens)


def test_large_bundled_font_keeps_cache_exception_glyphs_in_format_one():
    path=Path(__file__).resolve().parents[2]/'wasm/playground/assets/three_divs64.ttf'
    exceptions=0
    with TTFont(path) as font:
        for lookup in font['GSUB'].table.LookupList.Lookup:
            for extension in lookup.SubTable:
                if extension.ExtensionLookupType!=6:continue
                table=extension.ExtSubTable
                affected=any(0x7f00<=font.getGlyphID(name)<=0x7fff for name in table.Coverage.glyphs)
                if affected:
                    assert table.Format==1
                    exceptions+=1
    assert exceptions>0


def test_tiny_circuit_can_retain_the_smaller_format_one_encoding(tmp_path,monkeypatch):
    circuit=Circuit()
    argument=circuit.argument(0,1)
    output=Value((circuit.NOT(argument.bits[0]),))
    attach=tables._attach_layout
    sizes={}
    for mode in (False,True,None):
        path=tmp_path/f'tiny-{mode}.ttf'
        with monkeypatch.context() as patch:
            if mode is not None:
                def layout(*args,**kwargs):
                    kwargs['class_singletons']=mode
                    return attach(*args,**kwargs)
                patch.setattr(tables,'_attach_layout',layout)
            emit_font(deepcopy(circuit),[output],{},['i1'],['i1'],path,
                      lookup_batch_size=1,lookup_coalescing=False)
        sizes[mode]=path.stat().st_size
        with NativeFont(path) as font:
            assert font.invoke(0)==1
            assert font.invoke(1)==0
    assert sizes[False]<sizes[True]
    assert sizes[None]==sizes[False]
