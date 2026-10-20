# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Persistent system HarfBuzz harness; no game implementation."""
import ctypes as C
import ctypes.util
from contextlib import ExitStack
from pathlib import Path
from fontTools.ttLib import TTFont

P, U, I = C.c_void_p, C.c_uint, C.c_int


class Info(C.Structure):
    _fields_ = [('gid', U), ('mask', U), ('cluster', U), ('v1', U), ('v2', U)]


class Position(C.Structure):
    _fields_ = [('ax', I), ('ay', I), ('dx', I), ('dy', I), ('v', U)]


class Feature(C.Structure):
    _fields_ = [('tag', U), ('value', U), ('start', U), ('end', U)]


class Shaper:
    def __init__(self, path):
        # Validate the file before allocating native resources.
        with TTFont(path) as font:
            self.order = font.getGlyphOrder()
        self.hb = C.CDLL(ctypes.util.find_library('harfbuzz') or '/opt/homebrew/lib/libharfbuzz.dylib')

        def bind(name, result, arguments):
            function = getattr(self.hb, name)
            function.restype, function.argtypes = result, arguments
            return function

        self.storage = C.create_string_buffer(Path(path).read_bytes())
        with ExitStack() as cleanup:
            self.blob = bind('hb_blob_create', P, [P, U, I, P, P])(
                self.storage, len(self.storage)-1, 2, None, None)
            cleanup.callback(bind('hb_blob_destroy', None, [P]), self.blob)
            self.face = bind('hb_face_create', P, [P, U])(self.blob, 0)
            cleanup.callback(bind('hb_face_destroy', None, [P]), self.face)
            self.font = bind('hb_font_create', P, [P])(self.face)
            cleanup.callback(bind('hb_font_destroy', None, [P]), self.font)
            bind('hb_ot_font_set_funcs', None, [P])(self.font)
            self.create = bind('hb_buffer_create', P, [])
            self.destroy = bind('hb_buffer_destroy', None, [P])
            self.add = bind('hb_buffer_add', None, [P, U, U])
            self.content = bind('hb_buffer_set_content_type', None, [P, I])
            self.direction = bind('hb_buffer_set_direction', None, [P, I])
            self.guess = bind('hb_buffer_guess_segment_properties', None, [P])
            self.shape = bind('hb_shape', None, [P, P, P, U])
            self.length = bind('hb_buffer_get_length', U, [P])
            self.info = bind('hb_buffer_get_glyph_infos', P, [P, P])
            self.positions = bind('hb_buffer_get_glyph_positions', P, [P, P])
            self.version = bind('hb_version_string', C.c_char_p, [])().decode()
            self._cleanup = cleanup.pop_all()

    def run(self, source, enabled=True, transport=False):
        if self.font is None:
            raise RuntimeError('Cannot shape with a closed font')
        buffer = self.create()
        try:
            self.content(buffer, 1)
            self.direction(buffer, 4)
            for index, char in enumerate(source):
                codepoint = ord(char)
                if transport:
                    codepoint = 0xe100 + (codepoint if 32 <= codepoint <= 126 else 127)
                self.add(buffer, codepoint, index)
            self.guess(buffer)
            disabled = Feature(int.from_bytes(b'liga', 'big'), 0, 0, 0xffffffff)
            self.shape(self.font, buffer, None if enabled else C.byref(disabled), 0 if enabled else 1)
            count = self.length(buffer)
            info = C.cast(self.info(buffer, None), C.POINTER(Info))
            positions = C.cast(self.positions(buffer, None), C.POINTER(Position))
            return [(self.order[info[i].gid], positions[i].ax, positions[i].dx, positions[i].dy)
                    for i in range(count)]
        finally:
            self.destroy(buffer)

    def close(self):
        self._cleanup.close()
        self.font = None
