# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""LLVM IR compiled to bounded, executable GSUB Boolean circuits."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'shared'))

from .compiler import LLVMError, Limits, build, compile_ir

__all__ = ['LLVMError', 'Limits', 'build', 'compile_ir']
