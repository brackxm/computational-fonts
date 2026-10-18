"""Regressions from the full WASM review: decoding, literals and reference VM."""
import pytest

from wasmfont.runtime import NativeFont
from wasmfont.frontend import binary, load, parse_text, unsigned_leb, validate
from wasmfont.ir import Function, execute, parse_binary, uleb
from wasmfont.reference.lowering import compile_module
from wasmfont.compiler import compile_source
from wasmfont.oracle import execute_binary


def memory_binary(store, extended):
    """A single memory containing AB; load/store at offset one."""
    def section(tag, payload):
        return bytes([tag]) + unsigned_leb(len(payload)) + payload

    memarg = (b'\x40\x00' if extended else b'\x00') + b'\x01'
    if store:
        # Store 90 at 0+1, then load address 1 normally.
        instructions = b'\x41\x00\x41\xda\x00\x3a' + memarg + b'\x41\x01\x2d\x00\x00'
    else:
        instructions = b'\x41\x00\x2d' + memarg
    body = b'\x00' + instructions + b'\x0b'
    return (b'\0asm\x01\0\0\0' + section(1, b'\x01\x60\x00\x01\x7f') +
            section(3, b'\x01\x00') + section(5, b'\x01\x00\x01') +
            section(7, b'\x01\x03run\x00\x00') +
            section(10, b'\x01' + unsigned_leb(len(body)) + body) +
            section(11, b'\x01\x00\x41\x00\x0b\x02AB'))


@pytest.mark.parametrize('store', [False, True], ids=['load', 'store'])
@pytest.mark.parametrize('extended', [False, True], ids=['ordinary', 'explicit-memory-zero'])
def test_memory_operands_are_decoded_or_rejected(tmp_path, store, extended):
    data = memory_binary(store, extended)
    expected = 90 if store else 66
    assert execute_binary(data, 'run', [], [[]]) == [{'values': [str(expected)]}]
    source = tmp_path / 'memory.wasm'
    source.write_bytes(data)
    font = tmp_path / 'memory.ttf'
    if extended:
        for action in (lambda: parse_binary(source), lambda: load(source),
                       lambda: compile_source(source, font, export='run')):
            with pytest.raises(NotImplementedError, match='memory'):
                action()
        assert not font.exists()
        assert not font.with_suffix('.json').exists()
    else:
        module, _ = load(source)
        assert module.invoke('run', []) == [expected]
        compile_source(source, font, export='run')
        with NativeFont(font) as native:
            assert native.invoke() == expected


LITERAL_LOCATIONS = [('instruction', 32), ('instruction', 64),
                     ('global', 32), ('global', 64), ('data', 32)]


def literal_module(location, width, literal):
    ty = f'i{width}'
    if location == 'global':
        return f'(module (global {ty} ({ty}.const {literal})) (func (export "run") (result {ty}) global.get 0))'
    if location == 'data':
        return f'(module (memory 1) (data (i32.const {literal}) "A"))'
    return f'(module (func (export "run") (result {ty}) {ty}.const {literal}))'


@pytest.mark.parametrize('location,width', LITERAL_LOCATIONS)
@pytest.mark.parametrize('below_minimum', [False, True], ids=['too-large', 'too-negative'])
@pytest.mark.parametrize('hexadecimal', [False, True], ids=['decimal', 'hexadecimal'])
def test_reject_out_of_range_literals_before_binary_encoding(tmp_path, location, width,
                                                           below_minimum, hexadecimal):
    value = -(1 << (width - 1)) - 1 if below_minimum else 1 << width
    literal = hex(value) if hexadecimal else str(value)
    wat = literal_module(location, width, literal)
    with pytest.raises(ValueError, match='literal out of range'):
        parse_text(wat)
    source = tmp_path / 'invalid.wat'
    source.write_text(wat)
    font = tmp_path / 'invalid.ttf'
    with pytest.raises(ValueError, match='literal out of range'):
        compile_source(source, font)
    assert not font.exists()


@pytest.mark.parametrize('location,width', LITERAL_LOCATIONS)
@pytest.mark.parametrize('boundary', ['minimum', 'signed-maximum', 'unsigned-maximum'])
def test_valid_literal_boundaries_still_encode(location, width, boundary):
    value = {'minimum': -(1 << (width - 1)), 'signed-maximum': (1 << (width - 1)) - 1,
             'unsigned-maximum': (1 << width) - 1}[boundary]
    # Data offsets can be valid literals even when instantiation would trap.
    validate(binary(parse_text(literal_module(location, width, str(value)))))


def compare_reference_and_font(tmp_path, wat, cases):
    source = tmp_path / 'program.wat'
    source.write_text(wat)
    module, data = load(source)
    fn = module.functions[module.exports['run'][1]]
    references = execute_binary(data, 'run', fn.params, cases)
    font = tmp_path / 'program.ttf'
    compile_source(source, font, export='run')
    with NativeFont(font) as native:
        for args, reference in zip(cases, references):
            assert 'trap' not in reference
            expected = tuple(int(value) & ((1 << int(ty[1:])) - 1)
                             for value, ty in zip(reference['values'], fn.results))
            assert tuple(module.invoke('run', args)) == expected
            actual = native.invoke(*args)
            assert ((actual,) if len(fn.results) == 1 else actual) == expected


@pytest.mark.parametrize('width', [32, 64])
@pytest.mark.parametrize('operation', ['clz', 'ctz', 'popcnt'])
def test_reference_counting_is_unary(tmp_path, width, operation):
    ty = f'i{width}'
    wat = f'(module (func (export "run") (param {ty}) (result {ty}) local.get 0 {ty}.{operation}))'
    cases = [(value,) for value in (0, 1, 7, 1 << (width - 1), (1 << width) - 1, -7)]
    compare_reference_and_font(tmp_path, wat, cases)


@pytest.mark.parametrize('width', [32, 64])
def test_reference_counting_preserves_other_operands(tmp_path, width):
    ty = f'i{width}'
    wat = f'''(module (func (export "run") (param {ty}) (result {ty})
      {ty}.const 11 local.get 0 {ty}.popcnt {ty}.add))'''
    compare_reference_and_font(tmp_path, wat, [(0,), (7,), (-1,)])


@pytest.mark.parametrize('branch', ['br 0', 'i32.const 1 br_if 0',
                                  'i32.const 0 br_table 0 0', 'block br 1 end'])
def test_branching_out_of_if_skips_else(tmp_path, branch):
    wat = f'''(module (func (export "run") (param i32) (result i32)
      local.get 0 if {branch} else i32.const 22 return end i32.const 11))'''
    compare_reference_and_font(tmp_path, wat, [(0,), (1,), (-1,)])


def test_branching_out_of_else_does_not_reenter_it(tmp_path):
    wat = '''(module (func (export "run") (param i32) (result i32)
      local.get 0 if i32.const 11 return else br 0 end i32.const 22))'''
    compare_reference_and_font(tmp_path, wat, [(0,), (1,)])


@pytest.mark.parametrize('body', [
    'block i32.const 99 br 0 end i32.const 42',
    'block i32.const 99 i32.const 0 br_table 0 0 end i32.const 42',
    'block block i32.const 99 br 1 end end i32.const 42',
    'i32.const 99 i32.const 42 return',
    'i32.const 99 i32.const 42 br 0',
    'block i32.const 99 i32.const 42 br 1 end i32.const 5',
])
def test_branches_and_returns_discard_temporary_operands(tmp_path, body):
    compare_reference_and_font(tmp_path, f'(module (func (export "run") (result i32) {body}))', [()])


def test_untaken_branch_preserves_operands(tmp_path):
    wat = '''(module (func (export "run") (param i32) (result i32)
      block i32.const 99 local.get 0 br_if 0 drop end i32.const 42))'''
    compare_reference_and_font(tmp_path, wat, [(0,), (1,)])


def test_function_branch_preserves_results_only_when_taken(tmp_path):
    wat = '''(module (func (export "run") (param i32) (result i32)
      i32.const 99 i32.const 42 local.get 0 br_if 0 drop drop i32.const 7))'''
    compare_reference_and_font(tmp_path, wat, [(0,), (1,)])


def test_branch_unwinding_preserves_the_stack_below_its_label(tmp_path):
    wat = '''(module (func (export "run") (param i32) (result i32)
      i32.const 5 block block i32.const 99 local.get 0 br_if 1 drop end end
      i32.const 6 i32.add))'''
    compare_reference_and_font(tmp_path, wat, [(0,), (1,)])


def test_branch_table_can_target_the_function_label(tmp_path):
    wat = '''(module (func (export "run") (param i32) (result i32)
      i32.const 99 i32.const 42 local.get 0 br_table 0 0))'''
    compare_reference_and_font(tmp_path, wat, [(0,), (1,), (-1,)])


def test_loop_backedge_discards_temporary_operands(tmp_path):
    wat = '''(module (func (export "run") (param i32) (result i32) (local i32)
      local.get 0 local.set 1
      block loop local.get 1 i32.eqz br_if 1
        local.get 1 i32.const 1 i32.sub local.set 1 i32.const 99 br 0
      end end i32.const 42))'''
    compare_reference_and_font(tmp_path, wat, [(0,), (1,), (3,)])


@pytest.mark.parametrize('signature,body', [
    ('', 'i32.const 99 return'),
    ('(result i32 i64)', 'i32.const 99 i32.const 42 i64.const 84 return'),
])
def test_return_preserves_the_declared_result_arity(tmp_path, signature, body):
    compare_reference_and_font(tmp_path, f'(module (func (export "run") {signature} {body}))', [()])


LEGACY_ADD = '''(module
  (func (export "run") (param i32 i32) (result i32)
    local.get 0 local.get 1 i32.add)
  (func unreachable))'''


def insert_section(data, tag, payload):
    """Insert an ordinary core section without altering the function bodies."""
    pos = 8
    while pos < len(data) and data[pos] < tag:
        size, start = uleb(data, pos + 1)
        pos = start + size
    return data[:pos] + bytes([tag]) + unsigned_leb(len(payload)) + payload + data[pos:]


@pytest.mark.parametrize('tag,payload', [(2, b'\0'), (4, b'\0'), (8, b'\1'), (9, b'\0')],
                         ids=['imports', 'tables', 'trapping-start', 'elements'])
def test_legacy_compilation_rejects_unsupported_binary_sections(tmp_path, tag, payload):
    data = insert_section(binary(parse_text(LEGACY_ADD)), tag, payload)
    validate(data)
    if tag == 8:
        assert 'trap' in execute_binary(data, 'run', ['i32', 'i32'], [(7, 9)])[0]
    source = tmp_path / 'unsupported.wasm'
    source.write_bytes(data)
    font = tmp_path / 'unsupported.ttf'
    with pytest.raises(NotImplementedError, match='section'):
        compile_module(source, font)
    assert not font.exists()


@pytest.mark.parametrize('field', ['(start 1)', '(table 0 funcref)', '(import "env" "unused" (func))'])
def test_legacy_compilation_rejects_unsupported_wat_fields(tmp_path, field):
    source = tmp_path / 'unsupported.wat'
    source.write_text(LEGACY_ADD[:-1] + field + ')')
    font = tmp_path / 'unsupported.ttf'
    with pytest.raises(NotImplementedError, match='module field'):
        compile_module(source, font)
    assert not font.exists()


def test_legacy_compilation_validates_original_binary(tmp_path):
    module = parse_text(LEGACY_ADD)
    module.exports['run'] = (0, 99)
    source = tmp_path / 'invalid.wasm'
    source.write_bytes(binary(module))
    font = tmp_path / 'invalid.ttf'
    with pytest.raises(ValueError, match='V8 rejected'):
        compile_module(source, font)
    assert not font.exists()


@pytest.mark.parametrize('suffix', ['.wat', '.wasm'])
def test_legacy_compilation_preserves_function_selection(tmp_path, suffix):
    from wasmfont.harfbuzz import run

    wat = '''(module
      (func (param i32 i32) (result i32) local.get 0 local.get 1 i32.add)
      (func (export "run") (param i32 i32) (result i32)
        (i32.sub (local.get 0) (local.get 1))))'''
    data = binary(parse_text(wat))
    source = tmp_path / ('selected' + suffix)
    if suffix == '.wat':
        source.write_text(wat)
    else:
        source.write_bytes(data)
    font = tmp_path / 'selected.ttf'
    lowered = compile_module(source, font, function_index=1)
    cases = [(7, 9), (-1, 1), (0x80000000, -1)]
    for args, reference in zip(cases, execute_binary(data, 'run', ['i32', 'i32'], cases)):
        assert lowered.decode(run(font, lowered.encode(*args))) == int(reference['values'][0]) & 0xffffffff


@pytest.mark.parametrize('offset', ['(i32.const)', '(i32.const 0 1)',
                                  '(i32.const 0 4294967296)', '(i32.const (i32.const 0))'])
def test_data_offsets_require_exactly_one_integer_immediate(tmp_path, offset):
    wat = f'''(module (memory 1) (data {offset} "A")
      (func (export "run") (result i32) i32.const 0 i32.load8_u))'''
    with pytest.raises(ValueError, match='data offset'):
        parse_text(wat)
    source = tmp_path / 'invalid-data.wat'
    source.write_text(wat)
    font = tmp_path / 'invalid-data.ttf'
    with pytest.raises(ValueError, match='data offset'):
        compile_source(source, font)
    assert not font.exists()
    assert not font.with_suffix('.json').exists()


@pytest.mark.parametrize('payload', ['', 'A'])
def test_active_data_requires_declared_memory(tmp_path, payload):
    wat = f'''(module (data $bytes (i32.const 0) "{payload}")
      (func (export "run") (result i32) memory.size))'''
    with pytest.raises(ValueError, match='memory'):
        parse_text(wat)
    source = tmp_path / 'missing-memory.wat'
    source.write_text(wat)
    font = tmp_path / 'missing-memory.ttf'
    with pytest.raises(ValueError, match='memory'):
        compile_source(source, font)
    assert not font.exists()
    assert not font.with_suffix('.json').exists()


def test_binary_writer_does_not_invent_memory_for_data():
    module = parse_text('(module)')
    module.segments.append((0, b''))
    with pytest.raises(ValueError, match='memory'):
        binary(module)


@pytest.mark.parametrize('pages,payload,body', [(0, '', 'memory.size'), (1, 'A', 'i32.const 0 i32.load8_u')])
def test_active_data_preserves_declared_memory(tmp_path, pages, payload, body):
    wat = f'''(module (memory {pages} {pages}) (data $bytes (i32.const 0) "{payload}")
      (func (export "run") (result i32) {body}))'''
    compare_reference_and_font(tmp_path, wat, [()])
    module, data = load(tmp_path / 'program.wat')
    assert binary(module) == data


@pytest.mark.parametrize('signature,body', [
    ('', 'i32.const 99 return unreachable'),
    ('(result i32)', 'i32.const 99 i32.const 42 return unreachable'),
    ('(result i64)', 'i32.const 99 i64.const -1 return unreachable'),
    ('(result i32 i64)', 'i32.const 99 i32.const 42 i64.const 84 return unreachable'),
])
def test_legacy_return_unwinds_to_declared_results(tmp_path, signature, body):
    wat = f'(module (func (export "run") {signature} {body}))'
    data = binary(parse_text(wat))
    source = tmp_path / 'return.wasm'
    source.write_bytes(data)
    fn = parse_binary(source)[0]
    reference = execute_binary(data, 'run', [], [()])[0]
    expected = [int(value) & ((1 << int(ty[1:])) - 1)
                for value, ty in zip(reference['values'], fn.results)]
    assert execute(fn, []) == expected


@pytest.mark.parametrize('results,code', [(['i32'], []), (['i32', 'i64'], [('i64.const', 42)])])
def test_legacy_return_rejects_missing_results(results, code):
    with pytest.raises(ValueError, match='underflow'):
        execute(Function([], results, [], code + [('return', None)]), [])
