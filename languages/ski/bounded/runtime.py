"""Structural input/output around ONE HarfBuzz call. No SKI reducer is imported."""
from __future__ import annotations
import ctypes as C
from ctypes.util import find_library
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from fontTools.ttLib import TTFont
from .syntax import ALPHABET, App, Leaf, parse, prefix, height
from .layout import VALUES, paths, validate


class InputOverflow(ValueError):
    """The input tree cannot be encoded. No shaping has occurred."""


class MachineError(RuntimeError):
    """Invalid configuration, failed shaping, or incomplete/corrupt output."""


def _load_configuration(path):
    try:
        meta = json.loads(path.read_text())
    except (ValueError, UnicodeError) as error:
        raise MachineError('invalid machine configuration JSON') from error
    if type(meta) is not dict:
        raise MachineError('machine configuration must be an object')
    if type(meta.get('schema')) is not int or meta['schema'] != 1:
        raise MachineError('unknown machine schema')
    required = {'depth': int, 'rounds': int, 'capacity': int,
                'font_sha256': str, 'chars': dict}
    for field, kind in required.items():
        if field not in meta or type(meta[field]) is not kind:
            raise MachineError(f'invalid or missing configuration field: {field}')
    try:
        validate(meta['depth'], meta['rounds'])
    except ValueError as error:
        raise MachineError(f'invalid machine configuration: {error}') from error
    digest = meta['font_sha256']
    if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
        raise MachineError('invalid configuration font digest')
    if any(type(name) is not str or type(codepoint) is not int
           for name, codepoint in meta['chars'].items()):
        raise MachineError('invalid configuration character map')
    return meta


class Info(C.Structure):
    _fields_ = [(name, C.c_uint) for name in ('codepoint', 'mask', 'cluster', 'var1', 'var2')]


class Feature(C.Structure):
    _fields_ = [(name, C.c_uint) for name in ('tag', 'value', 'start', 'end')]


@dataclass(frozen=True)
class Result:
    status: str
    expression: str
    steps: int
    glyphs: tuple[str, ...]


class HarfBuzz:
    """Small owned ctypes binding to the installed HarfBuzz OpenType shaper."""
    def __init__(self, path):
        self.font = None
        self.lib = C.CDLL(find_library('harfbuzz') or 'libharfbuzz.so.0')
        p, u = C.c_void_p, C.c_uint

        def bind(name, restype, args):
            fn = getattr(self.lib, name)
            fn.restype, fn.argtypes = restype, args
            return fn

        blob = bind('hb_blob_create', p, [p, u, u, p, p])
        face = bind('hb_face_create', p, [p, u])
        font = bind('hb_font_create', p, [p])
        self.destroy_blob = bind('hb_blob_destroy', None, [p])
        self.destroy_face = bind('hb_face_destroy', None, [p])
        self.destroy_font = bind('hb_font_destroy', None, [p])
        self.buffer = bind('hb_buffer_create', p, [])
        self.destroy_buffer = bind('hb_buffer_destroy', None, [p])
        self.add = bind('hb_buffer_add_utf8', None, [p, C.c_char_p, C.c_int, u, C.c_int])
        self.direction = bind('hb_buffer_set_direction', None, [p, C.c_int])
        self.script = bind('hb_buffer_set_script', None, [p, u])
        self.shape_full = bind('hb_shape_full', C.c_int,
                               [p, p, C.POINTER(Feature), u, C.POINTER(C.c_char_p)])
        self.length = bind('hb_buffer_get_length', u, [p])
        self.info = bind('hb_buffer_get_glyph_infos', C.POINTER(Info), [p, C.POINTER(u)])
        self.success = bind('hb_buffer_allocation_successful', C.c_int, [p])
        self.version = bind('hb_version_string', C.c_char_p, [])().decode()
        with TTFont(path) as ft:
            self.names = ft.getGlyphOrder()
        data = Path(path).read_bytes()
        storage = C.create_string_buffer(data)
        # DUPLICATE memory mode: HarfBuzz owns a copy, not the Python buffer.
        b = blob(storage, len(data), 0, None, None)
        f = face(b, 0)
        self.font = font(f)
        self.destroy_face(f)
        self.destroy_blob(b)

    def shape(self, text, features=None):
        if self.font is None:
            raise MachineError('HarfBuzz font is closed')
        b = self.buffer()
        try:
            data = text.encode('utf8')
            self.add(b, data, len(data), 0, len(data))
            self.direction(b, 4)  # HB_DIRECTION_LTR
            self.script(b, int.from_bytes(b'Latn', 'big'))
            fs = {'calt': 1} if features is None else features
            arr = (Feature * len(fs))(*(Feature(int.from_bytes(tag.encode(), 'big'),
                                                v, 0, 0xffffffff) for tag, v in fs.items()))
            shapers = (C.c_char_p * 2)(b'ot', None)
            if not self.shape_full(self.font, b, arr, len(arr), shapers) or not self.success(b):
                raise MachineError('HarfBuzz shaping failed')
            n, info = self.length(b), self.info(b, None)
            return tuple(self.names[info[i].codepoint] for i in range(n))
        finally:
            self.destroy_buffer(b)

    def close(self):
        if self.font is not None:
            self.destroy_font(self.font)
            self.font = None


class Machine:
    """Parse -> fixed tree tape -> hb_shape_full once -> validated tree tape."""
    def __init__(self, font):
        font = Path(font)
        self.meta = _load_configuration(font.with_suffix('.json'))
        self.depth, self.rounds = self.meta['depth'], self.meta['rounds']
        if hashlib.sha256(font.read_bytes()).hexdigest() != self.meta['font_sha256']:
            raise MachineError('font/configuration digest mismatch')
        with TTFont(font) as ft:
            actual_cmap = {v: k for k, v in ft.getBestCmap().items()}
        if actual_cmap != self.meta['chars']:
            raise MachineError('font/configuration character map mismatch')
        self.ps = paths(self.depth)
        self.ix = {p: i for i, p in enumerate(self.ps)}
        if self.meta['capacity'] != len(self.ps):
            raise MachineError('invalid tree capacity')
        expected_chars = {'seek'} | {f'f{i}' for i in range(self.rounds + 1)}
        expected_chars.update(f'n{i}_{v}' for i in range(len(self.ps)) for v in VALUES)
        expected_chars.update(f'{tag}{i}' for tag in ('t', 'q') for i in range(len(self.ps)))
        if set(self.meta['chars']) != expected_chars:
            raise MachineError('character map does not match machine depth/rounds')
        self.hb = HarfBuzz(font)

    def encode(self, source, fuel=None):
        fuel = self.rounds if fuel is None else fuel
        if type(fuel) is not int or not 0 <= fuel <= self.rounds:
            raise ValueError('fuel outside compiled range')
        t = parse(source)
        if height(t) > self.depth:
            raise InputOverflow(f'input depth {height(t)} exceeds {self.depth}')
        values = ['E'] * len(self.ps)

        def put(node, path):
            values[self.ix[path]] = node.value if isinstance(node, Leaf) else 'A'
            if isinstance(node, App):
                put(node.left, path + '0')
                put(node.right, path + '1')

        put(t, '')
        gs = ['seek'] + [f'n{i}_{v}' for i, v in enumerate(values)]
        for i in range(len(values)):
            gs.extend((f't{i}', f'q{i}'))
        gs.append(f'f{fuel}')
        return ''.join(chr(self.meta['chars'][g]) for g in gs), fuel

    def decode(self, glyphs, initial_fuel):
        """Read output state only. Does not select, simulate, or fix reductions."""
        if type(initial_fuel) is not int or not 0 <= initial_fuel <= self.rounds:
            raise ValueError('fuel outside compiled range')
        gs, n = tuple(glyphs), len(self.ps)
        if len(gs) != 3 * n + 2:
            raise MachineError(f'wrong tape length {len(gs)}')
        if gs[0] not in ('normal', 'budget', 'overflow'):
            raise MachineError(f'unfinished machine: {gs[0]}')
        values = []
        for i, g in enumerate(gs[1:n + 1]):
            if not g.startswith(f'n{i}_'):
                raise MachineError('main slot lost its address')
            values.append(g.split('_', 1)[1])
        for i in range(n):
            if gs[n + 1 + 2 * i:n + 3 + 2 * i] != (f't{i}', f'q{i}'):
                raise MachineError('dirty scratch bank')
        seen = set()

        def get(path):
            if path not in self.ix:
                raise MachineError('tree exceeds capacity')
            i = self.ix[path]
            seen.add(i)
            v = values[i]
            if v == 'A':
                return App(get(path + '0'), get(path + '1'))
            if len(v) != 1 or v not in ALPHABET:
                raise MachineError('missing or invalid node')
            return Leaf(v)

        t = get('')
        if any(v != 'E' for i, v in enumerate(values) if i not in seen):
            raise MachineError('orphaned nodes')
        if gs[-1] not in {f'f{i}' for i in range(initial_fuel + 1)}:
            raise MachineError('invalid fuel register')
        remaining = int(gs[-1][1:])
        return Result(gs[0], prefix(t), initial_fuel - remaining, gs)

    def run(self, source, fuel=None):
        encoded, initial = self.encode(source, fuel)
        return self.decode(self.hb.shape(encoded), initial)

    def close(self):
        self.hb.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
