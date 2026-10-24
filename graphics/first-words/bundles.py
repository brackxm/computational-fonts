# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Write reproducible distribution ZIPs without local timestamps or permissions."""

from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED


def write_bundle(output, entries):
    with ZipFile(output, 'w', compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(entries):
            info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, data, compresslevel=9)
