# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Persistent native HarfBuzz test driver for game fonts."""
import ctypes
from pathlib import Path
import sys

from fontTools.ttLib import TTFont
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'languages'/'shared'))
from fontcircuit import harfbuzz as hb


def transport(source):
    return '\ue000'+''.join(chr(0xe100+(ord(c) if ' '<=c<='~' else
                 32 if c in '\t\r\n' else 127)) for c in source)+'\ue001'


class NativeFont:
    def __init__(self,path):
        self.data=ctypes.create_string_buffer(Path(path).read_bytes())
        self.blob=hb.blob_create(self.data,len(self.data)-1,2,None,None)
        self.face=hb.face_create(self.blob,0)
        self.font=hb.font_create(self.face)
        with TTFont(path) as font:self.order=font.getGlyphOrder()

    def shape(self,source):
        return self.shape_text(transport(source))

    def shape_text(self,text):
        """Shape trusted protocol text, also usable with test-only cmap aliases."""
        buffer=hb.buffer_create()
        try:
            hb.set_content(buffer,1)
            for i,c in enumerate(text):hb.add(buffer,ord(c),i)
            hb.guess(buffer);hb.shape(self.font,buffer,None,0)
            infos=ctypes.cast(hb.getinfo(buffer,None),ctypes.POINTER(hb.GlyphInfo))
            return [self.order[infos[i].codepoint] for i in range(hb.length(buffer))]
        finally:hb.buffer_destroy(buffer)

    def close(self):
        hb.font_destroy(self.font);hb.face_destroy(self.face);hb.blob_destroy(self.blob)
