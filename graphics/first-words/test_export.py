# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Check reproducible exports, retired assets and invalid-data handling."""

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import generate_artwork as artwork


class ArtworkExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        artwork.ART.clear()
        artwork.CATEGORIES.clear()
        base = json.loads((artwork.HERE / 'approved_samples.json').read_text())
        for function in (artwork.food, artwork.animals, artwork.home):
            function(base)
        for function in (artwork.clothes_and_toys, artwork.transport, artwork.nature,
                         artwork.body, artwork.additional_words):
            function()

    def export(self, output):
        with redirect_stdout(io.StringIO()):
            artwork.export(output)

    def copy_sources(self, destination):
        destination.mkdir()
        for file in artwork.HERE.iterdir():
            if file.is_file() and file.suffix in {'.py', '.json', '.txt', '.md'}:
                shutil.copyfile(file, destination / file.name)

    def test_export_bundle_is_reproducible_and_self_contained(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'export'
            self.export(output)
            first = (output / 'first-words-svg.zip').read_bytes()
            with patch('zipfile.time.localtime', return_value=(2030, 6, 7, 8, 9, 10, 4, 158, 0)):
                self.export(output)
            self.assertEqual(first, (output / 'first-words-svg.zip').read_bytes())
            with ZipFile(output / 'first-words-svg.zip') as archive:
                self.assertEqual(sum(n.startswith('artwork/') for n in archive.namelist()), 391)
                self.assertIn('bundles.py', archive.namelist())
                self.assertIn('plurals.json', archive.namelist())
                self.assertNotIn('first-words-svg.zip', archive.read('index.html').decode())
                for info in archive.infolist():
                    self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0))

    def test_removed_plural_does_not_survive_export_or_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            output, source = workspace / 'export', workspace / 'source'
            self.export(output)
            self.copy_sources(source)
            data = json.loads((source / 'plurals.json').read_text())
            data['apple'] = []
            (source / 'plurals.json').write_text(json.dumps(data))
            (output / 'previews' / 'new-50.svg').write_text('obsolete preview')
            extra = output / 'artwork' / 'custom.svg'
            extra.write_text('unrelated source')
            with patch.object(artwork, 'HERE', source):
                self.export(output)
            self.assertFalse((output / 'artwork' / 'plurals' / 'apple.svg').exists())
            self.assertFalse((output / 'previews' / 'new-50.svg').exists())
            self.assertEqual(extra.read_text(), 'unrelated source')
            with ZipFile(output / 'first-words-svg.zip') as archive:
                self.assertNotIn('artwork/plurals/apple.svg', archive.namelist())
                self.assertNotIn('artwork/custom.svg', archive.namelist())
                self.assertNotIn('previews/new-50.svg', archive.namelist())

    def test_invalid_aliases_leave_existing_assets_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            output, source = workspace / 'export', workspace / 'source'
            self.copy_sources(source)
            data = json.loads((source / 'aliases.json').read_text())
            data['cat'].append('apple')
            (source / 'aliases.json').write_text(json.dumps(data))
            asset = output / 'artwork' / 'apple.svg'
            asset.parent.mkdir(parents=True)
            asset.write_text('existing asset')
            with patch.object(artwork, 'HERE', source):
                with self.assertRaisesRegex(ValueError, 'Ambiguous label'):
                    self.export(output)
            self.assertEqual(asset.read_text(), 'existing asset')
            self.assertFalse((output / 'manifest.json').exists())


if __name__ == '__main__':
    unittest.main()
