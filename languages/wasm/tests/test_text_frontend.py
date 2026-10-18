"""WAT comments and declaration syntax must survive text-to-binary conversion."""
import pytest

from wasmfont.runtime import NativeFont
from wasmfont.frontend import binary, load, parse_text
from wasmfont.compiler import compile_source
from wasmfont.oracle import execute_binary


@pytest.mark.parametrize('ending', ['\n', '\r', '\r\n'], ids=['LF', 'CR', 'CRLF'])
@pytest.mark.parametrize('body', [
    '(module;; comment{end}(func (export "run") (result i32) i32.const 42))',
    '(module (func $run;; comment{end}(export "run") (result i32) i32.const 42))',
    '(module (func (export "run") (param $x;; comment{end}i32) (result i32) i32.const 42))',
    '(module (func (export "run") (result i32) i32.const;; comment{end}42))',
    '(module (func (export "run") (result i32) i32.const 42;; comment{end}))',
])
def test_line_comments_can_separate_tokens(tmp_path, ending, body):
    wat = body.format(end=ending)
    module = parse_text(wat)
    args = [0] * len(module.functions[0].params)
    assert module.invoke('run', args) == [42]
    data = binary(module)
    assert execute_binary(data, 'run', module.functions[0].params, [args]) == [{'values': ['42']}]
    source = tmp_path / 'comments.wat'
    source.write_text(wat)
    path = source.with_suffix('.ttf')
    compile_source(source, path, export='run')
    with NativeFont(path) as font:
        assert font.invoke(*args) == 42


@pytest.mark.parametrize('comment', [';; trailing comment', '(; outer (; nested ;) comment ;)'])
def test_comments_at_end_of_module(tmp_path, comment):
    source = tmp_path / 'trailing.wat'
    source.write_text('(module (func (export "run") (result i32) i32.const 42))' + comment)
    module, _ = load(source)
    assert module.invoke('run', []) == [42]


def test_comment_delimiters_in_strings_are_data(tmp_path):
    source = tmp_path / 'strings.wat'
    source.write_text('''(module (memory 1) (data (i32.const 0) "A;;B(;C;)")
      (func (export "run;;name") (result i32) i32.const 1 i32.load8_u))''')
    module, data = load(source)
    assert module.segments == [(0, b'A;;B(;C;)')]
    assert execute_binary(data, 'run;;name', [], [()]) == [{'values': ['59']}]
    path = source.with_suffix('.ttf')
    compile_source(source, path, export='run;;name')
    with NativeFont(path) as font:
        assert font.invoke() == 59


@pytest.mark.parametrize('wat', [
    '(module (func (export) (result i32) i32.const 42))',
    '(module (func (export "run" "ignored") (result i32) i32.const 42))',
    '(module (type (func (result i32))) (func (export "run") (type) i32.const 42))',
    '(module (type (func (result i32))) (func (export "run") (type 0 9999999999) i32.const 42))',
    '(module (type (func (result i32))) (func (export "run") (type "0") i32.const 42))',
    '(module (type (func (result i64))) (type (func (result i32))) '
    '(func (export "run") (type 0) (type 1) i32.const 42))',
    '(module (type (func)) (func (export "run") (type 0) (type 0)))',
    '(module (memory (export) 1) (func (export "run") (result i32) memory.size))',
    '(module (memory (export "m" "ignored") 1) (func (export "run") (result i32) memory.size))',
    '(module (global (export) i32 (i32.const 3)) (func (export "run") (result i32) global.get 0))',
    '(module (global (export "g" "ignored") i32 (i32.const 3)) '
    '(func (export "run") (result i32) global.get 0))',
    '(module (func (result i32) i32.const 42) (export))',
    '(module (func (result i32) i32.const 42) (export "run"))',
    '(module (func (result i32) i32.const 42) (export "run" (func 0) "ignored"))',
    '(module (func (result i32) i32.const 42) (export "run" (func)))',
    '(module (func (result i32) i32.const 42) (export "run" (func 0 1)))',
    '(module (func (result i32) i32.const 42) (export "run" "func"))',
])
def test_malformed_declarations_are_rejected_before_encoding(tmp_path, wat):
    with pytest.raises(ValueError):
        parse_text(wat)
    source = tmp_path / 'invalid.wat'
    source.write_text(wat)
    path = source.with_suffix('.ttf')
    with pytest.raises(ValueError):
        compile_source(source, path)
    assert not path.exists()
    assert not path.with_suffix('.json').exists()


def test_multiple_exports_and_one_type_use_remain_valid(tmp_path):
    source = tmp_path / 'exports.wat'
    source.write_text('''(module
      (type $sig (func (param i32) (result i32)))
      (memory $m (export "m1") (export "m2") 0 0)
      (global $g (export "g1") (export "g2") i32 (i32.const 3))
      (func $f (export "run") (export "alias") (type $sig)
        (param $x i32) (result i32) (local $tmp i32)
        local.get $x global.get $g i32.add local.tee $tmp)
      (export "third" (func $f)) (export "memory" (memory $m))
      (export "global" (global $g)))''')
    module, data = load(source)
    assert len(module.exports) == 9
    for export in ('run', 'alias', 'third'):
        assert execute_binary(data, export, ['i32'], [(7,)]) == [{'values': ['10']}]
        assert module.invoke(export, [7]) == [10]
    path = source.with_suffix('.ttf')
    compile_source(source, path, export='run')
    with NativeFont(path) as font:
        assert font.invoke(7) == 10
