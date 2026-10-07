# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0

"""Build the bounded plain-PBM renderer. Requires FontTools."""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from netpbm import PBM, MAX_SIZE, build_font as build_netpbm


def build_font(output):
    build_netpbm(output, PBM)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("pbm-font.ttf"))
    build_font(parser.parse_args().output)


if __name__ == "__main__":
    main()
