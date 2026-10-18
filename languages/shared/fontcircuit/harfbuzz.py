"""Actual HarfBuzz shaping of glyph-token programs via PUA Unicode encoding."""
import ctypes
import ctypes.util
from pathlib import Path
from fontTools.ttLib import TTFont


def load_harfbuzz():
    """Resolve the system library, including Homebrew's macOS installation."""
    candidates = [ctypes.util.find_library('harfbuzz'),
                  'libharfbuzz.so.0', 'libharfbuzz.0.dylib', 'harfbuzz.dll']
    errors = []
    for candidate in dict.fromkeys(name for name in candidates if name):
        try:
            return ctypes.CDLL(candidate)
        except OSError as exc:
            errors.append(str(exc))
    raise RuntimeError(
        'HarfBuzz shared library not found. Install HarfBuzz with your system '
        'package manager (macOS: brew install harfbuzz; Debian/Ubuntu: '
        'apt install libharfbuzz0b). Tried: ' + '; '.join(errors))


hb=load_harfbuzz()
def bind(name, restype, args):
 f=getattr(hb,name);f.restype=restype;f.argtypes=args;return f
P=ctypes.c_void_p; U=ctypes.c_uint; I=ctypes.c_int
blob_create=bind('hb_blob_create',P,[P,U,I,P,P]);blob_destroy=bind('hb_blob_destroy',None,[P])
face_create=bind('hb_face_create',P,[P,U]);face_destroy=bind('hb_face_destroy',None,[P])
font_create=bind('hb_font_create',P,[P]);font_destroy=bind('hb_font_destroy',None,[P])
buffer_create=bind('hb_buffer_create',P,[]);buffer_destroy=bind('hb_buffer_destroy',None,[P])
set_content=bind('hb_buffer_set_content_type',None,[P,I]);add=bind('hb_buffer_add',None,[P,U,U]);guess=bind('hb_buffer_guess_segment_properties',None,[P])
shape=bind('hb_shape',None,[P,P,P,U]);length=bind('hb_buffer_get_length',U,[P]);getinfo=bind('hb_buffer_get_glyph_infos',P,[P,P])
class GlyphInfo(ctypes.Structure):
 _fields_=[('codepoint',U),('mask',U),('cluster',U),('var1',U),('var2',U)]

def run(font_path, tokens):
 data=Path(font_path).read_bytes(); storage=ctypes.create_string_buffer(data)
 blob=blob_create(storage,len(data),2,None,None);face=face_create(blob,0);font=font_create(face);buf=buffer_create()
 try:
  set_content(buf,1)
  with TTFont(font_path) as tt:
   order=tt.getGlyphOrder(); cmap=tt.getBestCmap(); reverse={name:cp for cp,name in cmap.items()}
  for token in tokens:
   if token not in reverse: raise ValueError('glyph lacks Unicode mapping: '+token)
   add(buf,reverse[token],0)
  guess(buf);shape(font,buf,None,0)
  n=length(buf);ptr=getinfo(buf,None);infos=ctypes.cast(ptr,ctypes.POINTER(GlyphInfo))
  return [order[infos[i].codepoint] for i in range(n)]
 finally:
  buffer_destroy(buf);font_destroy(font);face_destroy(face);blob_destroy(blob)
