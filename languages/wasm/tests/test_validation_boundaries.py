"""Validation must hold at every public module and font entry point."""
import hashlib
import json
from pathlib import Path

import pytest
from fontTools.ttLib import TTFont

from wasmfont import runtime
from wasmfont.gsub.circuit import Circuit, emit_font
from wasmfont.runtime import NativeFont
from .test_review_regressions import LEGACY_ADD, insert_section
from wasmfont.frontend import binary, load, parse_text, validate
from wasmfont.module import load_binary
from wasmfont.compiler import compile_source
from wasmfont.oracle import execute_binary


ASSETS = Path(__file__).resolve().parents[1] / 'playground' / 'assets'


@pytest.fixture
def add_manifest():
    return json.loads((ASSETS / 'add.json').read_text())


def corrupt_manifest(manifest, case):
    if case == 'short-result': manifest['results'][0].pop()
    elif case == 'long-result': manifest['results'][0].append(manifest['results'][0][0])
    elif case == 'missing-result': manifest['results'] = []
    elif case == 'unknown-result-wire': manifest['results'][0][0] = 999999
    elif case == 'boolean-result-wire': manifest['results'][0][0] = True
    elif case == 'bad-result-type': manifest['result_types'] = ['f32']
    elif case == 'non-string-type': manifest['result_types'] = [32]
    elif case == 'non-list-parameters': manifest['parameter_types'] = 'i32'
    elif case == 'bad-parameter-type': manifest['parameter_types'][0] = 'f32'
    elif case == 'missing-flags': del manifest['flags']
    elif case == 'non-object-flags': manifest['flags'] = []
    elif case == 'bad-flag-name': manifest['flags'] = {'wrong': manifest['results'][0][0]}
    elif case == 'unknown-flag-wire': manifest['flags'] = {'trap.zero': 999999}
    elif case == 'null-entry': manifest['tape'][0] = None
    elif case == 'duplicate-wire': manifest['tape'][1]['wire'] = manifest['tape'][0]['wire']
    elif case == 'unordered-tape': manifest['tape'].reverse()
    elif case == 'negative-wire': manifest['tape'][0]['wire'] = -1
    elif case == 'boolean-wire': manifest['tape'][0]['wire'] = False
    elif case == 'bad-kind': manifest['tape'][0]['kind'] = 'unknown'
    elif case == 'bad-argument-index':
        next(entry for entry in manifest['tape'] if entry['kind'] == 'argument')['argument'] = 2
    elif case == 'bad-argument-bit':
        next(entry for entry in manifest['tape'] if entry['kind'] == 'argument')['bit'] = 32
    elif case == 'bad-constant':
        next(entry for entry in manifest['tape'] if entry['kind'] == 'constant')['constant'] = 2
    elif case == 'bad-hash': manifest['font_sha256'] = 'invalid'
    else: raise AssertionError(case)


@pytest.mark.parametrize('case', [
    'short-result', 'long-result', 'missing-result', 'unknown-result-wire', 'boolean-result-wire',
    'bad-result-type', 'non-string-type', 'non-list-parameters', 'bad-parameter-type',
    'missing-flags', 'non-object-flags', 'bad-flag-name', 'unknown-flag-wire', 'null-entry',
    'duplicate-wire', 'unordered-tape', 'negative-wire', 'boolean-wire', 'bad-kind',
    'bad-argument-index', 'bad-argument-bit', 'bad-constant', 'bad-hash',
])
def test_native_manifest_rejected_before_creating_shaper(tmp_path, monkeypatch, add_manifest, case):
    corrupt_manifest(add_manifest, case)
    manifest_path = tmp_path / 'invalid.json'
    manifest_path.write_text(json.dumps(add_manifest))
    monkeypatch.setattr(runtime, 'TokenShaper', lambda *args, **kwargs: pytest.fail('created shaper'))
    with pytest.raises(ValueError, match='ABI manifest'):
        NativeFont(ASSETS / 'add.ttf', manifest_path)


@pytest.mark.parametrize('root', [None, [], 42])
def test_native_manifest_requires_an_object(tmp_path, root):
    manifest = tmp_path / 'invalid.json'
    manifest.write_text(json.dumps(root))
    with pytest.raises(ValueError, match='ABI manifest'):
        NativeFont(ASSETS / 'add.ttf', manifest)


@pytest.mark.parametrize('case', ['renumbered-wires', 'gate-as-constant'])
def test_native_manifest_must_match_font_register_layout(tmp_path, add_manifest, case):
    if case == 'renumbered-wires':
        for entry in add_manifest['tape']: entry['wire'] += 1000
        add_manifest['results'] = [[wire + 1000 for wire in bits] for bits in add_manifest['results']]
        add_manifest['flags'] = {name: wire + 1000 for name, wire in add_manifest['flags'].items()}
    else:
        next(entry for entry in add_manifest['tape'] if entry['kind'] == 'gate')['kind'] = 'constant'
    manifest_path = tmp_path / 'wrong-layout.json'
    manifest_path.write_text(json.dumps(add_manifest))
    with pytest.raises(ValueError, match='register layout'):
        NativeFont(ASSETS / 'add.ttf', manifest_path)


def test_native_manifest_checks_register_cmap(tmp_path, add_manifest):
    path = tmp_path / 'wrong-cmap.ttf'
    with TTFont(ASSETS / 'add.ttf') as font:
        for table in font['cmap'].tables:
            if table.isUnicode() and 0xf0000 in table.cmap:
                table.cmap[0xf0000] = font.getGlyphOrder()[3]
        font.save(path)
    add_manifest['font_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_suffix('.json').write_text(json.dumps(add_manifest))
    with pytest.raises(ValueError, match='register layout'):
        NativeFont(path)


def test_valid_native_manifest_preserves_the_high_result_bit():
    with NativeFont(ASSETS / 'add.ttf') as font:
        assert font.invoke(0xffffffff, 0) == 0xffffffff


@pytest.mark.parametrize('width', [4, 128])
def test_native_manifest_preserves_generic_integer_circuits(tmp_path, width):
    circuit = Circuit()
    value = circuit.argument(0, width)
    path = tmp_path / 'identity.ttf'
    emit_font(circuit, [value], {}, [f'i{width}'], [f'i{width}'], path)
    with NativeFont(path) as font:
        for value in (0, (1 << width) - 1, 1 << (width - 1)):
            assert font.invoke(value) == value


@pytest.mark.parametrize('tag,payload', [(2, b'\0'), (4, b'\0'), (8, b'\1'), (9, b'\0')],
                         ids=['imports', 'tables', 'trapping-start', 'elements'])
def test_direct_loader_rejects_unsupported_sections(tmp_path, tag, payload):
    data = insert_section(binary(parse_text(LEGACY_ADD)), tag, payload)
    validate(data)
    if tag == 8:
        assert 'trap' in execute_binary(data, 'run', ['i32', 'i32'], [(7, 9)])[0]
    source = tmp_path / 'unsupported.wasm'
    source.write_bytes(data)
    for loader in (load_binary, load):
        with pytest.raises(NotImplementedError, match='unsupported module section'):
            loader(source)


@pytest.mark.parametrize('case', ['export-index', 'result-type'])
def test_direct_loader_validates_the_original_binary(tmp_path, case):
    module = parse_text(LEGACY_ADD)
    if case == 'export-index': module.exports['run'] = (0, 99)
    else: module.functions[0].code = [('i64.const', 42)]
    source = tmp_path / 'invalid.wasm'
    source.write_bytes(binary(module))
    with pytest.raises(ValueError, match='V8 rejected'):
        load_binary(source)


def test_direct_loader_still_executes_supported_modules(tmp_path):
    source = tmp_path / 'add.wasm'
    source.write_bytes(binary(parse_text(LEGACY_ADD)))
    assert load_binary(source).invoke('run', [7, 9]) == [16]


@pytest.mark.parametrize('index', ['-1', '-0x1', '-2', '1', '0xffffffff', '4294967296'])
def test_type_indices_must_be_unsigned_and_in_range(tmp_path, index):
    wat = f'''(module (type (func (result i32)))
      (func (export "run") (type {index}) i32.const 42))'''
    with pytest.raises(ValueError, match='index'):
        parse_text(wat)
    source = tmp_path / 'invalid-type.wat'
    source.write_text(wat)
    font = source.with_suffix('.ttf')
    with pytest.raises(ValueError, match='index'):
        compile_source(source, font)
    assert not font.exists()
    assert not font.with_suffix('.json').exists()


@pytest.mark.parametrize('index,ty', [(0, 'i32'), (1, 'i64')])
def test_valid_type_indices_keep_the_selected_signature(tmp_path, index, ty):
    source = tmp_path / 'valid-type.wat'
    source.write_text(f'''(module (type (func (result i32))) (type (func (result i64)))
      (func (export "run") (type {index}) {ty}.const 42))''')
    module, data = load(source)
    assert module.functions[0].results == [ty]
    assert execute_binary(data, 'run', [], [()]) == [{'values': ['42']}]
    path = source.with_suffix('.ttf')
    compile_source(source, path)
    with NativeFont(path) as font:
        assert font.invoke() == 42
