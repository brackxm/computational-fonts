# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0

"""Preflight generated artifacts before any build writes files."""
from itertools import combinations
from pathlib import Path

from .config import DISPLAY_FONT


def font_artifacts(output, *, timing=False):
    output = Path(output)
    artifacts = (output, output.with_suffix('.json'), output.with_suffix('.fea'))
    return artifacts + (output.with_suffix('.build.json'),) if timing else artifacts


def same_file(first, second):
    return (first.resolve() == second.resolve() or
            (first.exists() and second.exists() and first.samefile(second)))


def overlap(first, second):
    return any(same_file(a, b) for a in first for b in second)


def validate_outputs(output, inputs=(), *, timing=False):
    artifacts = font_artifacts(output, timing=timing)
    if any(same_file(a, b) for a, b in combinations(artifacts, 2)):
        raise ValueError('Output artifact paths must differ from each other')
    if overlap(artifacts, inputs):
        raise ValueError('Output artifacts must differ from input files')


def validate_machine_output(output):
    validate_outputs(output, timing=True)
    if overlap(font_artifacts(output, timing=True), font_artifacts(DISPLAY_FONT)):
        raise ValueError('Machine output requires a different path from the bundled visible font artifacts')
