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

from restore_inputs import EXTERNAL_INPUTS, restore


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
            with contextlib.redirect_stdout(io.StringIO()):
                restore(repo, output, commit, inputs)
            for name in EXTERNAL_INPUTS:
                self.assertEqual((output / name).read_bytes(), (repo / 'games/gardner/research' / name).read_bytes())

            first = EXTERNAL_INPUTS[0]
            previous = b'previous verified input'
            (output / first).write_bytes(previous)
            bad = dict(inputs, **{first: dict(inputs[first], sha256='0' * 64)})
            with self.assertRaisesRegex(ValueError, 'Frozen input mismatch'):
                restore(repo, output, commit, bad)
            self.assertEqual((output / first).read_bytes(), previous)
            self.assertFalse(list(output.rglob('.restore-*')))
            with self.assertRaisesRegex(ValueError, 'Artifact ref unavailable locally'):
                restore(repo, output, 'absent-ref', inputs)
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
