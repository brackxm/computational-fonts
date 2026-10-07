# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0

"""Build the bounded plain-PPM renderer. Requires FontTools."""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from netpbm import PPM, MAX_SIZE, MAX_SIZE_LIMIT, validate_max_size, build_font as build_netpbm


def build_font(output, *, max_size=MAX_SIZE):
    build_netpbm(output, PPM, max_size=max_size)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("ppm-font.ttf"))
    parser.add_argument("--max-size", type=int, default=MAX_SIZE, metavar="N",
                        help=f"maximum width and height (1–{MAX_SIZE_LIMIT}; default: {MAX_SIZE})")
    args = parser.parse_args()
    try:
        validate_max_size(args.max_size)
    except ValueError as error:
        parser.error(str(error))
    build_font(args.output, max_size=args.max_size)


if __name__ == "__main__":
    main()
