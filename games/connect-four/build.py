# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Build the independent, exhaustively certified Connect Four font."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE/'research'))
from kernel import build
from policy_io import read_json, source_bytes


def build_font(output):
    certificate = HERE/'research/winning-policy.json.gz'
    controller_path = HERE/'research/controller.json.gz'
    proof = read_json(HERE/'research/winning-policy-verification.json')
    source_hash = hashlib.sha256(source_bytes(certificate)).hexdigest()
    if not (proof.get('verified') is True and proof.get('empty_board') is True and
            proof.get('certificate_sha256') == source_hash and proof.get('maximum_plies') == 41):
        raise ValueError('Missing or stale complete empty-board certificate verification')
    controller_source = source_bytes(controller_path)
    controller_hash = hashlib.sha256(controller_source).hexdigest()
    validation = read_json(HERE/'research/font-verification.json')
    if validation.get('controller_sha256') != controller_hash or validation.get('certificate_sha256') != source_hash:
        raise ValueError('Controller needs binary-table and shaping validation before distribution')
    controller = json.loads(controller_source)
    if controller.get('certificate_sha256') != source_hash:
        raise ValueError('Controller does not identify the verified certificate')
    stats = build(controller, output)
    abi = {**stats, 'certificate_sha256': source_hash,
           'controller_sha256': controller_hash,
           'font_sha256': hashlib.sha256(output.read_bytes()).hexdigest()}
    output.with_suffix('.abi.json').write_text(json.dumps(abi, indent=2)+'\n')
    measurements = {key: stats[key] for key in ('glyphs', 'lookups', 'controller_modes', 'branch_modes',
                                               'priority_maps', 'column_profiles', 'profile_glyphs', 'driver_records', 'tape_registers',
                                               'turns', 'ttf_bytes', 'woff2_bytes')}
    output.with_suffix('.json').write_text(json.dumps(measurements, indent=2)+'\n')
    output.with_suffix('.independent.json').unlink()
    return measurements


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE/'connect-four-font.ttf')
    args = parser.parse_args()
    print(json.dumps(build_font(args.output), indent=2))
