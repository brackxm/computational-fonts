# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Check that real font serialization preserves an existing output on failure."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile

from build import HERE, bake, sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir', type=Path, default=HERE / 'build')
    args = parser.parse_args()
    manifest = json.loads((HERE / 'manifest.json').read_text())
    with tempfile.TemporaryDirectory(prefix='gardner-build-check-') as directory:
        directory = Path(directory)
        stem = directory / 'gardner-research'
        for suffix in ['.json', '.gsub', '.gdef']:
            shutil.copyfile(args.build_dir / ('gardner-research' + suffix), stem.with_suffix(suffix))
        output = stem.with_suffix('.ttf')
        previous = b'previous accepted output'
        output.write_bytes(previous)
        invalid = dict(manifest, font_sha256='0' * 64)
        try:
            bake(stem, invalid)
        except ValueError as error:
            assert str(error) == 'Rebuilt font differs from the accepted artifact'
        else:
            raise AssertionError('Mismatched rebuild was accepted')
        assert output.read_bytes() == previous, 'Failed build replaced the existing output'
        assert not list(directory.glob('.gardner-font-*')), 'Temporary font leaked'
        bake(stem, manifest)
        assert sha256(output) == manifest['font_sha256']
        assert not list(directory.glob('.gardner-font-*'))
    print(json.dumps(dict(status='pass', failed_build_preserves_output=True,
                          successful_build_byte_exact=True, temporary_fonts_cleaned=True,
                          font_sha256=manifest['font_sha256'], proof_searches=0)))


if __name__ == '__main__':
    main()
