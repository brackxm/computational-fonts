# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0

"""Build SKI's machine font and visible, ASCII-input evaluator font."""
import argparse
from pathlib import Path
import tempfile

from bounded.build import build
from bounded.config import DEFAULT_FONT
from bounded.layout import validate
from bounded.outputs import validate_machine_output
from bounded.visible import DISPLAY_FONT, build_visible, validate_visible_output


def build_font(output, *, depth=5, rounds=32):
    return build(output, depth, rounds)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--depth', type=int, default=5)
    parser.add_argument('--rounds', type=int, default=32)
    parser.add_argument('--output', '--out', type=Path)
    parser.add_argument('--visible', action='store_true', help='build a visible font at --output')
    args = parser.parse_args()
    try:
        validate(args.depth, args.rounds)
        # Reject custom bundled builds before either font or sidecar is written.
        if args.visible or args.output is None:
            validate_visible_output(args.output or DISPLAY_FONT, args.depth, args.rounds)
        if args.visible:
            with tempfile.TemporaryDirectory(prefix='ski-visible-build-') as td:
                machine = Path(td) / 'machine.ttf'
                build(machine, args.depth, args.rounds)
                build_visible(machine, args.output or DISPLAY_FONT)
        else:
            output = args.output or DEFAULT_FONT
            validate_machine_output(output)
            build(output, args.depth, args.rounds)
            if args.output is None:
                build_visible(output, DISPLAY_FONT)
    except ValueError as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
