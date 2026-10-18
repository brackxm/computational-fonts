"""Bounded two-state combinational Verilog compiled to OpenType GSUB."""

from pathlib import Path
import sys

# Both language frontends use the same bit-circuit backend and shaping ABI.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'shared'))
