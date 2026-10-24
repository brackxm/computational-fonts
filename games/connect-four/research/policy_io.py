# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Read independently generated JSON sources, optionally gzip compressed."""
import gzip
import json
from pathlib import Path


def source_bytes(path):
    path = Path(path)
    data = path.read_bytes()
    return gzip.decompress(data) if path.suffix == '.gz' else data


def read_json(path):
    return json.loads(source_bytes(path))
