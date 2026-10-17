# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""DOCX package and editable font embedding regression checks.

These tests do not establish compatibility with Word's shaping engine.
Run: python3 -m unittest discover -s specimens -p 'test_word.py'
"""

from dataclasses import replace
from pathlib import Path
from posixpath import dirname, join, normpath
import tempfile
import unittest
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from docx import Document

import build as specimens
import word


NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "w14": "http://schemas.microsoft.com/office/word/2010/wordml",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
}


class WordSpecimenTests(unittest.TestCase):
    def test_guid_byte_order(self):
        # A fixed mask catches GUID endianness mistakes that a round trip misses.
        key = "{00112233-4455-6677-8899-AABBCCDDEEFF}"
        expected = bytes.fromhex("ffeeddccbbaa99887766554433221100") * 2
        self.assertEqual(word.obfuscate_font(bytes(40), key), expected + bytes(8))

    def test_all_specimens(self):
        with tempfile.TemporaryDirectory() as tmp:
            for index, spec in enumerate(specimens.SPECS):
                with self.subTest(project=spec.folder):
                    path = Path(tmp) / f"{index}.docx"
                    word.build(spec, specimens.ROOT, specimens.BASE, specimens.font_family, path)
                    initial = path.read_bytes()
                    word.build(spec, specimens.ROOT, specimens.BASE, specimens.font_family, path)
                    self.assertEqual(path.read_bytes(), initial)
                    with ZipFile(path) as package:
                        self.assertIsNone(package.testzip())
                        self.check_package(package, spec)
                    # A separate OOXML consumer must accept the document too.
                    self.assertEqual(Document(path).core_properties.title, spec.title)

    def check_package(self, package, spec):
        table = ET.fromstring(package.read("word/fontTable.xml"))
        relations = ET.fromstring(package.read("word/_rels/fontTable.xml.rels"))
        links = {el.get("Id"): el.get("Target") for el in relations}
        paths = (specimens.BASE, specimens.ROOT / spec.folder / spec.font)
        for entry, path in zip(table, paths, strict=True):
            embedded = entry.find("w:embedRegular", NS)
            self.assertEqual(entry.get("{" + NS["w"] + "}name"), specimens.font_family(path))
            self.assertEqual(embedded.get("{" + NS["w"] + "}subsetted"), "false")
            key = embedded.get("{" + NS["w"] + "}fontKey")
            target = links[embedded.get("{" + NS["r"] + "}id")]
            blob = package.read(normpath(join("word", target)))
            self.assertEqual(word.obfuscate_font(blob, key), path.read_bytes())

        # Check every relationship, including font and licence parts.
        for name in package.namelist():
            if name.endswith(".rels"):
                parent = dirname(dirname(name))
                for rel in ET.fromstring(package.read(name)):
                    if rel.get("TargetMode") != "External":
                        target = rel.get("Target")
                        resolved = target.lstrip("/") if target.startswith("/") else normpath(join(parent, target))
                        self.assertIn(resolved, package.namelist())
        types = ET.fromstring(package.read("[Content_Types].xml"))
        self.assertTrue(any(el.get("ContentType") == word.FONT_CONTENT_TYPE for el in types))
        settings = ET.fromstring(package.read("word/settings.xml"))
        for name, value in (("embedTrueTypeFonts", "true"), ("embedSystemFonts", "true"),
                            ("saveSubsetFonts", "false")):
            self.assertEqual(settings.find("w:" + name, NS).get("{" + NS["w"] + "}val"), value)
        doc = ET.fromstring(package.read("word/document.xml"))
        rendered = [p for p in doc.findall(".//w:p", NS)
                    if p.find('w:pPr/w:pStyle[@w:val="Rendered"]', NS) is not None]
        for paragraph, example in zip(rendered, spec.examples, strict=True):
            self.assertEqual(len(paragraph.findall("w:r", NS)), 1)
            self.assertEqual("".join(paragraph.itertext()), example.source)
            self.assertEqual(paragraph.find("w:r/w:rPr/w14:ligatures", NS).get("{" + NS["w14"] + "}val"),
                             "standardContextual")
            self.assertIsNotNone(paragraph.find("w:r/w:rPr/w14:cntxtAlts", NS))
            self.assertIsNotNone(paragraph.find("w:r/w:rPr/w:noProof", NS))
        self.assertEqual(package.read("LICENSE.txt"), (specimens.ROOT / "LICENSE").read_bytes())
        self.assertEqual(package.read("THIRD_PARTY_NOTICES.txt"),
                         (specimens.ROOT / "THIRD_PARTY_NOTICES.md").read_bytes())

    def test_embedding_restrictions(self):
        from fontTools.ttLib import TTFont
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "restricted.ttf"
            with TTFont(specimens.BASE) as font:
                font["OS/2"].fsType = 2
                font.save(path)
            spec = replace(specimens.SPECS[0], folder=tmp, font=path.name)
            with self.assertRaisesRegex(ValueError, "editable embedding"):
                word.build(spec, specimens.ROOT, specimens.BASE, specimens.font_family,
                           Path(tmp) / "restricted.docx")


if __name__ == "__main__":
    unittest.main()
