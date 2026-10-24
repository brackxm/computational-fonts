# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Compare unpruned and pruned builds, adapted from bounded/bench.py."""
import argparse
import contextlib
import json
from pathlib import Path
import sys
import tempfile
import time

from .build import build
from .layout import validate
from .profile import profile, validate_samples


def benchmark(*, configurations=((4, 8), (5, 32)), samples=30, warmups=5):
    validate_samples(samples, warmups)
    configurations = tuple(configurations)
    if not configurations:
        raise ValueError('at least one configuration is required')
    for depth, rounds in configurations:
        validate(depth, rounds)
    reports = []
    with tempfile.TemporaryDirectory(prefix='ski-benchmark-') as td:
        for depth, rounds in configurations:
            for optimized in (False, True):
                output = Path(td) / f'd{depth}-b{rounds}-{optimized}.ttf'
                start = time.perf_counter()
                with contextlib.redirect_stdout(sys.stderr):
                    build(output, depth, rounds, optimize=optimized)
                elapsed = time.perf_counter() - start
                report = profile(output, samples=samples, warmups=warmups)
                report.update(optimized=optimized, build_seconds=elapsed)
                reports.append(report)
    return {'configurations': reports,
            'note': 'Sequential same-engine measurements; timings depend on hardware, load and engine version.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--depth', type=int, help='benchmark one depth/round configuration')
    parser.add_argument('--rounds', type=int)
    parser.add_argument('--samples', type=int, default=30)
    parser.add_argument('--warmups', type=int, default=5)
    args = parser.parse_args()
    if (args.depth is None) != (args.rounds is None):
        parser.error('--depth and --rounds must be supplied together')
    configurations = ((args.depth, args.rounds),) if args.depth is not None else ((4, 8), (5, 32))
    try:
        report = benchmark(configurations=configurations, samples=args.samples, warmups=args.warmups)
    except (OSError, ValueError, RuntimeError) as error:
        parser.error(str(error))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
