# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0

"""Shared Netpbm test fixtures; no font is built on import."""

from pathlib import Path
import subprocess
import sys
import tempfile

def odf_text(node):
    value = node.text or ""
    for child in node:
        if child.tag == "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}s":
            value += " " * int(child.get("{urn:oasis:names:tc:opendocument:xmlns:text:1.0}c", "1"))
        else:
            value += odf_text(child)
        value += child.tail or ""
    return value


class FontFixture:
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="netpbm-tests-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.directory = Path(cls.temporary.name)
        cls.generated = cls.directory / "nested" / "test.ttf"
        subprocess.run([sys.executable, str(cls.project / "build.py"), "--output", "nested/test.ttf"],
                       cwd=cls.directory, check=True, capture_output=True, timeout=60)

