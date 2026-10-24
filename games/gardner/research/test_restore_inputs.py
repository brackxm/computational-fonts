# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Exercise restoration against real Git objects without large font assets."""
import contextlib
import hashlib
import io
from pathlib import Path
import subprocess
import tempfile
import unittest

from restore_inputs import ARTIFACT_REF, EXTERNAL_INPUTS, resolve_ref, restore


class RestoreTests(unittest.TestCase):
    def test_verified_restore_and_failure_preservation(self):
        with tempfile.TemporaryDirectory(prefix='gardner-restore-check-') as directory:
            root = Path(directory)
            repo, output = root / 'repo', root / 'output'
            repo.mkdir()

            def git(*args):
                return subprocess.check_output(['git', *args], cwd=repo, stderr=subprocess.PIPE, text=True).strip()

            git('init', '-q')
            inputs = {}
            for name in EXTERNAL_INPUTS:
                data = ('frozen ' + name).encode()
                path = repo / 'games/gardner/research' / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                inputs[name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
            git('add', '.')
            git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                '-c', 'commit.gpgsign=false', 'commit', '-qm', 'Frozen test inputs')
            commit = git('rev-parse', 'HEAD')
            # An ordinary clone fetches the artifact branch without creating a local branch.
            with self.assertRaisesRegex(ValueError, 'git fetch origin'):
                resolve_ref(repo, None)
            remote = 'refs/remotes/origin/' + ARTIFACT_REF
            local = 'refs/heads/' + ARTIFACT_REF
            git('update-ref', remote, commit)
            self.assertEqual(resolve_ref(repo, None), commit)
            with contextlib.redirect_stdout(io.StringIO()):
                restore(repo, output, None, inputs)
            for name in EXTERNAL_INPUTS:
                self.assertEqual((output / name).read_bytes(), (repo / 'games/gardner/research' / name).read_bytes())

            # Local artifacts take precedence; explicit refs never silently fall back.
            git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                '-c', 'commit.gpgsign=false', 'commit', '--allow-empty', '-qm', 'Local artifact tip')
            local_commit = git('rev-parse', 'HEAD')
            git('update-ref', local, local_commit)
            self.assertEqual(resolve_ref(repo, None), local_commit)
            self.assertEqual(resolve_ref(repo, remote), commit)
            self.assertEqual(resolve_ref(repo, commit), commit)
            git('update-ref', '-d', local)
            self.assertEqual(resolve_ref(repo, None), commit)

            first = EXTERNAL_INPUTS[0]
            previous = b'previous verified input'
            (output / first).write_bytes(previous)
            bad = dict(inputs, **{first: dict(inputs[first], sha256='0' * 64)})
            with self.assertRaisesRegex(ValueError, 'Frozen input mismatch'):
                restore(repo, output, commit, bad)
            self.assertEqual((output / first).read_bytes(), previous)
            self.assertFalse(list(output.rglob('.restore-*')))
            with self.assertRaisesRegex(ValueError, 'Artifact ref unavailable locally') as missing:
                restore(repo, output, 'absent-ref', inputs)
            self.assertIn('Use --ref', str(missing.exception))
            self.assertNotIn('git fetch', str(missing.exception))
            self.assertEqual((output / first).read_bytes(), previous)

            git('rm', 'games/gardner/research/' + first)
            git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                '-c', 'commit.gpgsign=false', 'commit', '-qm', 'Missing test input')
            with self.assertRaisesRegex(ValueError, 'Artifact ref lacks'):
                restore(repo, output, 'HEAD', inputs)
            self.assertEqual((output / first).read_bytes(), previous)
            self.assertFalse(list(output.rglob('.restore-*')))


if __name__ == '__main__':
    unittest.main()
