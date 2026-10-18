"""Bounded integer WebAssembly compilation to OpenType GSUB fonts."""

from pathlib import Path
import sys

# Keep repository-local CLI imports usable without installing a package.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'shared'))
