"""System library discovery and actionable errors across host platforms."""
import pytest
from wasmfont import harfbuzz


def test_discovered_library(monkeypatch):
    library = object()
    monkeypatch.setattr(harfbuzz.ctypes.util, 'find_library', lambda name: '/system/libharfbuzz.dylib')
    loaded = []

    def load(path):
        loaded.append(path)
        return library

    monkeypatch.setattr(harfbuzz.ctypes, 'CDLL', load)
    assert harfbuzz.load_harfbuzz() is library
    assert loaded == ['/system/libharfbuzz.dylib']


def test_library_fallback(monkeypatch):
    library = object()
    monkeypatch.setattr(harfbuzz.ctypes.util, 'find_library', lambda name: None)

    def load(path):
        if path == 'libharfbuzz.0.dylib':
            return library
        raise OSError('unavailable')

    monkeypatch.setattr(harfbuzz.ctypes, 'CDLL', load)
    assert harfbuzz.load_harfbuzz() is library


def test_missing_library(monkeypatch):
    monkeypatch.setattr(harfbuzz.ctypes.util, 'find_library', lambda name: None)

    def load(path):
        raise OSError('unavailable: ' + path)

    monkeypatch.setattr(harfbuzz.ctypes, 'CDLL', load)
    with pytest.raises(RuntimeError, match='Install HarfBuzz'):
        harfbuzz.load_harfbuzz()
