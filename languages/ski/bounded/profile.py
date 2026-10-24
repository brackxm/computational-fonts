# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Same-engine machine-font profiling, adapted from bounded/profile_v41.py."""
import argparse
import hashlib
import json
import math
import platform
import statistics
import time
from pathlib import Path

import fontTools
from fontTools.ttLib import TTFont

from .config import DEFAULT_FONT
from .runtime import InputOverflow, Machine

PROGRAMS = ('I a', 'K a b', 'S K K a', 'S a b (K c d)',
            'K a (S I I (S I I))', 'S (I a) b (I c)')


def validate_samples(samples, warmups):
    if type(samples) is not int or samples < 2:
        raise ValueError('samples must be an integer >= 2')
    if type(warmups) is not int or warmups < 0:
        raise ValueError('warmups must be a nonnegative integer')


def profile(font=DEFAULT_FONT, *, samples=30, warmups=5):
    """Time only HarfBuzz.shape; encode beforehand and decode outside timing."""
    validate_samples(samples, warmups)
    font = Path(font)
    with TTFont(font) as ft:
        gsub = ft['GSUB'].table
        feature = next((r.Feature for r in gsub.FeatureList.FeatureRecord if r.FeatureTag == 'calt'), None)
        if feature is None:
            raise ValueError('profiling requires a machine font with calt; visible fonts use rlig')
        indices = feature.LookupListIndex
        if feature.LookupCount != len(indices) or len(set(indices)) != len(indices):
            raise ValueError('machine schedule must have distinct active lookup indices')
        types = {}
        for lookup in gsub.LookupList.Lookup:
            key = str(lookup.LookupType)
            types[key] = types.get(key, 0) + 1
        stats = {'font_bytes': font.stat().st_size, 'glyphs': len(ft.getGlyphOrder()),
                 'lookups': gsub.LookupList.LookupCount, 'active_lookups': len(indices),
                 'lookup_types': types}
    measurements = {}
    with Machine(font) as machine:
        for program in PROGRAMS:
            try:
                text, fuel = machine.encode(program)
            except InputOverflow:
                measurements[program] = {'status': 'input_overflow'}
                continue
            observed = machine.hb.shape(text)
            result = machine.decode(observed, fuel)
            for _ in range(warmups):
                if machine.hb.shape(text) != observed:
                    raise RuntimeError('nondeterministic shaping output')
            durations = []
            for _ in range(samples):
                start = time.perf_counter_ns()
                actual = machine.hb.shape(text)
                durations.append((time.perf_counter_ns() - start) / 1e6)
                if actual != observed:
                    raise RuntimeError('nondeterministic shaping output')
            measurements[program] = {
                'status': result.status, 'steps': result.steps,
                'median_ms': statistics.median(durations),
                'p95_ms': sorted(durations)[math.ceil(.95 * samples) - 1],
            }
        return {
            'python': platform.python_version(), 'platform': platform.platform(),
            'fonttools': fontTools.__version__, 'harfbuzz': machine.hb.version,
            'font_sha256': hashlib.sha256(font.read_bytes()).hexdigest(),
            'depth': machine.depth, 'rounds': machine.rounds,
            'samples': samples, 'warmups': warmups,
            'measurement': 'HarfBuzz binding calls only; encoding and decoding excluded; milliseconds',
            **stats, 'measurements': measurements,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--font', type=Path, default=DEFAULT_FONT)
    parser.add_argument('--samples', type=int, default=30)
    parser.add_argument('--warmups', type=int, default=5)
    args = parser.parse_args()
    try:
        report = profile(args.font, samples=args.samples, warmups=args.warmups)
    except (OSError, ValueError, RuntimeError) as error:
        parser.error(str(error))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
