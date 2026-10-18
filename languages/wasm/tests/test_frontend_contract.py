"""Text validation must preserve token kinds, declaration phases and export order."""
import pytest

from wasmfont.compiler import compile_source
from wasmfont.frontend import load, parse_text
from wasmfont.oracle import execute_binary
from wasmfont.runtime import NativeFont


@pytest.mark.parametrize('inline', [False, True], ids=['standalone-first', 'inline-first'])
def test_export_style_preserves_default_entry(tmp_path, inline):
    first = ('(func $first (export "first") (result i32) i32.const 11)' if inline else
             '(func $first (result i32) i32.const 11) (export "first" (func $first))')
    source = tmp_path / 'exports.wat'
    source.write_text(f'(module {first} (func (export "second") (result i32) i32.const 22))')
    module, data = load(source)
    assert list(module.exports) == ['first', 'second']
    assert execute_binary(data, 'first', [], [()]) == [{'values': ['11']}]
    assert execute_binary(data, 'second', [], [()]) == [{'values': ['22']}]
    font = tmp_path / 'exports.ttf'
    manifest = compile_source(source, font)
    assert manifest['export'] == 'first'
    with NativeFont(font) as native:
        assert native.invoke() == 11


def test_mixed_export_kinds_follow_module_field_order(tmp_path):
    wat = '''(module
      (export "first" (func $run))
      (global $g (export "global-inline") i32 (i32.const 3))
      (export "memory-explicit" (memory $m))
      (memory $m (export "memory-inline") 0 0)
      (func $run (export "function-inline") (export "alias") (result i32) i32.const 11)
      (export "global-explicit" (global $g))
      (func (export "last") (result i32) i32.const 22))'''
    expected = ['first', 'global-inline', 'memory-explicit', 'memory-inline',
                'function-inline', 'alias', 'global-explicit', 'last']
    assert list(parse_text(wat).exports) == expected
    source = tmp_path / 'mixed.wat'
    source.write_text(wat)
    module, _ = load(source)
    assert list(module.exports) == expected
    font = source.with_suffix('.ttf')
    assert compile_source(source, font)['export'] == 'first'
    with NativeFont(font) as native:
        assert native.invoke() == 11


@pytest.mark.parametrize('field,descriptor', [
    ('(func $x (export "duplicate"))', 'func'),
    ('(memory $x (export "duplicate") 0 0)', 'memory'),
    ('(global $x (export "duplicate") i32 (i32.const 0))', 'global'),
])
@pytest.mark.parametrize('standalone_first', [False, True])
def test_duplicate_exports_across_styles_are_rejected(field, descriptor, standalone_first):
    standalone = f'(export "duplicate" ({descriptor} $x))'
    fields = [standalone, field] if standalone_first else [field, standalone]
    with pytest.raises(ValueError, match='duplicate export'):
        parse_text('(module ' + ' '.join(fields) + ')')


QUOTED_TOKENS = [
    '("module" (func (export "run") (result i32) i32.const 7))',
    '(module ("func" (export "run") (result i32) i32.const 7))',
    '(module (func "$run" (export "run") (result i32) i32.const 7))',
    '(module (func (export "run") (result i32) "i32.const" 7))',
    '(module (func (export "run") (result i32) ("i32.const" 7)))',
    '(module (func (export "run") (result i32) i32.const "7"))',
    '(module (func (export "run") (result i64) i64.const "7"))',
    '(module (func (export "run") (result "i32") i32.const 7))',
    '(module (func (export "run") (param "i32") (result i32) local.get 0))',
    '(module (func (export "run") (local "i32")))',
    '(module (func (export "run") (param "$x" i32)))',
    '(module (type (func (param "i32"))))',
    '(module (memory "1"))',
    '(module (global "i32" (i32.const 7)))',
    '(module (global i32 (i32.const "7")))',
    '(module (memory 1) (data (i32.const "0") "A"))',
    '(module (func (export "run") (result i32) block (result "i32") i32.const 7 end))',
    '(module (func (export "run") block br "0" end))',
    '(module (func (export "run") block i32.const 0 br_table "0" end))',
    '(module (func (export "run") block "$label" end "$label"))',
    '(module (func (export "run") "nop"))',
    '(module (func (export "run") block "end"))',
    '(module (func (export "run") (if (i32.const 1) ("then") (else))))',
    '(module (memory 1) (func (export "run") (result i32) i32.const 0 i32.load "offset=0"))',
    '(module (func ("export" "run") (result i32) i32.const 7))',
]


OUT_OF_ORDER_DECLARATIONS = [
    '(module (func (export "run") (param $a i32) (local $x i32) '
    '(param $b i32) (result i32) local.get $x))',
    '(module (func (export "run") (local i32) (param i32)))',
    '(module (func (export "run") (local i32) (result i32) i32.const 7))',
    '(module (func (export "run") (result i32) (param i32) local.get 0))',
    '(module (type (func (param i32))) (func (export "run") (param i32) (type 0)))',
    '(module (type (func)) (func (export "run") (local i32) (type 0)))',
    '(module (type (func)) (func (type 0) (export "run")))',
    '(module (func (param i32) (export "run")))',
    '(module (func (local i32) (export "run")))',
    '(module (func (export "run") nop (local i32)))',
    '(module (func (export "run") nop (param i32)))',
    '(module (func nop (export "run")))',
]


@pytest.mark.parametrize('wat', QUOTED_TOKENS + OUT_OF_ORDER_DECLARATIONS)
def test_invalid_text_is_rejected_before_font_generation(tmp_path, wat):
    with pytest.raises((ValueError, NotImplementedError)):
        parse_text(wat)
    source = tmp_path / 'invalid.wat'
    source.write_text(wat)
    font = source.with_suffix('.ttf')
    with pytest.raises((ValueError, NotImplementedError)):
        compile_source(source, font)
    assert not font.exists()
    assert not font.with_suffix('.json').exists()


def test_valid_declaration_phases_and_quoted_data(tmp_path):
    source = tmp_path / 'valid.wat'
    source.write_text('''(module $module
      (type $signature (func (param i32) (param i32) (result i32) (result i32)))
      (memory $memory 1)
      (global $global i32 (i32.const 3))
      (data $data (i32.const 0) "i32.const" "\\00\\ff")
      (func $run (export "run") (export "café") (type $signature)
        (param $a i32) (param $b i32) (result i32) (result i32)
        (local $x i32) (local $y i32)
        local.get $a local.set $x local.get $b local.set $y
        local.get $x global.get $global i32.add local.get $y)
      (func (export "implicit") (type $signature) (local $x i32)
        local.get 0 local.tee $x local.get 1))''')
    module, data = load(source)
    assert module.segments == [(0, b'i32.const\x00\xff')]
    assert list(module.exports) == ['run', 'café', 'implicit']
    for export, expected in [('run', [10, 11]), ('café', [10, 11]), ('implicit', [7, 11])]:
        assert execute_binary(data, export, ['i32', 'i32'], [(7, 11)]) == [
            {'values': [str(value) for value in expected]}]
        font = tmp_path / (export + '.ttf')
        compile_source(source, font, export=export)
        with NativeFont(font) as native:
            assert native.invoke(7, 11) == tuple(expected)
