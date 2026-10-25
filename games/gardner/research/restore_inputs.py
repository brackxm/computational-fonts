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


def resolve_ref(repo, ref):
    candidates = [ref] if ref is not None else [
        'refs/heads/' + ARTIFACT_REF,
        'refs/remotes/origin/' + ARTIFACT_REF,
    ]
    for candidate in candidates:
        try:
            return subprocess.check_output(
                ['git', 'rev-parse', '--verify', '--end-of-options', candidate + '^{commit}'],
                cwd=repo, text=True, stderr=subprocess.PIPE).strip()
        except subprocess.CalledProcessError:
            pass
    requested = ref if ref is not None else ARTIFACT_REF + ' (local branch or fetched origin ref)'
    recovery = ('Use --ref with an existing local ref or commit.' if ref is not None else
                f'Fetch explicitly with:\n  git fetch origin refs/heads/{ARTIFACT_REF}:'
                f'refs/remotes/origin/{ARTIFACT_REF}')
    raise ValueError(f'Artifact ref unavailable locally: {requested}.\n'
                     f'{recovery}\nNo download was attempted.')


def restore(repo, target, ref, inputs):
    commit = resolve_ref(repo, ref)
    target.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.restore-', dir=target) as directory:
        staged = []
        for index, name in enumerate(EXTERNAL_INPUTS):
            expected = inputs[name]
            draft = Path(directory) / str(index)
            with draft.open('wb') as stream:
                result = subprocess.run(
                    ['git', 'cat-file', 'blob', f'{commit}:games/gardner/research/{name}'],
                    cwd=repo, stdout=stream, stderr=subprocess.PIPE)
            if result.returncode:
                raise ValueError(f'Artifact ref lacks {name}: {commit}')
            with draft.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            if draft.stat().st_size != expected['bytes'] or digest != expected['sha256']:
                raise ValueError(f'Frozen input mismatch: {name}')
            staged.append((name, draft))
        # A later missing/corrupt blob must not leave a partially restored set.
        for name, draft in staged:
            destination = target / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            draft.replace(destination)
            print('Restored verified input:', name, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ref', help='Exact local ref or commit; default: artifact branch, then its fetched origin ref')
    args = parser.parse_args()
    repo = Path(subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=HERE, text=True).strip())
    manifest = json.loads((HERE / 'manifest.json').read_text())
    try:
        restore(repo, HERE, args.ref, manifest['inputs'])
    except ValueError as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
