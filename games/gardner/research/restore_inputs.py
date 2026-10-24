# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Restore frozen research inputs from a local Git ref, without proof searches."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ARTIFACT_REF = 'codex/gardner-research-artifacts-20261024'
EXTERNAL_INPUTS = (
    'inputs/boundaries.records29',
    'inputs/game-base.gamepack',
    'inputs/game-base.ttf',
    'inputs/policy.tree.xz',
)


def restore(repo, target, ref, inputs):
    try:
        commit = subprocess.check_output(
            ['git', 'rev-parse', '--verify', '--end-of-options', ref + '^{commit}'],
            cwd=repo, text=True, stderr=subprocess.PIPE).strip()
    except subprocess.CalledProcessError as error:
        raise ValueError(f'Artifact ref unavailable locally: {ref}. '
                         'Obtain the preserved artifact branch first; no download was attempted.') from error
    for name in EXTERNAL_INPUTS:
        expected = inputs[name]
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.restore-', dir=destination.parent) as directory:
            draft = Path(directory) / 'input'
            with draft.open('wb') as stream:
                result = subprocess.run(
                    ['git', 'cat-file', 'blob', f'{commit}:games/gardner/research/{name}'],
                    cwd=repo, stdout=stream, stderr=subprocess.PIPE)
            if result.returncode:
                raise ValueError(f'Artifact ref lacks {name}: {ref}')
            with draft.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            if draft.stat().st_size != expected['bytes'] or digest != expected['sha256']:
                raise ValueError(f'Frozen input mismatch: {name}')
            draft.replace(destination)
        print('Restored verified input:', name, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ref', default=ARTIFACT_REF, help='Local branch or commit containing the frozen inputs')
    args = parser.parse_args()
    repo = Path(subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=HERE, text=True).strip())
    manifest = json.loads((HERE / 'manifest.json').read_text())
    try:
        restore(repo, HERE, args.ref, manifest['inputs'])
    except ValueError as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
