# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Bounded, lossless sharing between OpenType extension-subtable trees."""
from copy import copy

from fontTools.ttLib.tables.DefaultTable import DefaultTable
from fontTools.ttLib.tables.otBase import (
    OffsetToWriter, OTLOffsetOverflowError, OTTableWriter,
)


def compact_layout(font, tag='GSUB'):
    """Keep a smaller pure-Python layout encoding when all offsets still fit.

    Lookup indices, records, coverages and glyph IDs are unchanged. Only trees
    under extension wrappers share additional storage. FontTools' ordinary
    header layout and no-sharing guards remain intact. Unsupported trees and
    offset overflows retain the existing encoding; no native repacker is needed.
    """
    if tag not in font or not hasattr(font[tag], 'table'):
        return 0
    original = font.getTableData(tag)
    try:
        packed = _pack_extensions(font, tag)
    except OTLOffsetOverflowError:
        return 0
    # Sanitizers charge repeated traversal work against the encoded table's
    # length. Avoid excessive reuse in clock-heavy layouts such as Backgammon.
    # https://github.com/harfbuzz/harfbuzz/blob/main/src/hb-sanitize.hh
    # A conservative twofold ceiling retains the old representation rather
    # than padding a table or relying on a larger host sanitization budget.
    if packed is None or len(packed)*2 < len(original) or len(packed) >= len(original):
        return 0
    replacement = DefaultTable(tag)
    replacement.data = packed
    font[tag] = replacement
    return len(original)-len(packed)


def _walk(root):
    visited, pending = set(), [root]
    while pending:
        node = pending.pop()
        if id(node) in visited:
            continue
        visited.add(id(node))
        yield node
        pending.extend(item.subWriter for item in node.items
                       if hasattr(item, 'subWriter'))


def _pack_extensions(font, tag, *, max_scope=60000):
    writer = OTTableWriter(tableTag=tag)
    font[tag].table.compile(writer, font)
    writer._doneWriting({})
    headers, extension_tables = [], []
    writer._gatherTables(headers, extension_tables, {})
    headers.reverse()
    at = 0
    for node in headers:
        node.pos = at
        at += node.getDataLength()
    header_size = at
    header_ids = {id(node) for node in headers}
    wrappers = [node for node in headers if hasattr(node, 'Extension')]
    if not wrappers:
        return None

    groups, pending, known, size = [], [], set(), 0
    for wrapper in wrappers:
        references = [item for item in wrapper.items if hasattr(item, 'subWriter')]
        if len(references) != 1 or references[0].offsetSize != 4:
            return None
        root = references[0].subWriter
        graph = list(_walk(root))
        if any(hasattr(node, 'DontShare') or id(node) in header_ids for node in graph):
            return None
        graph = set(graph)
        cost = sum(node.getDataLength() for node in graph-known)
        if pending and size+cost > max_scope:
            groups.append(pending)
            pending, known, size = [], set(), 0
            cost = sum(node.getDataLength() for node in graph)
        pending.append(root)
        known.update(graph)
        size += cost
    if pending:
        groups.append(pending)

    parts = []
    for roots in groups:
        copies = {}

        def clone(node):
            if id(node) not in copies:
                result = copy(node)
                copies[id(node)] = result
                result.items = tuple(
                    OffsetToWriter(clone(item.subWriter), item.offsetSize)
                    if hasattr(item, 'subWriter') else item for item in node.items)
            return copies[id(node)]

        shared, merged = {}, []
        for root in roots:
            node = clone(root)
            node._doneWriting(shared, shareExtension=True)
            merged.append(shared.setdefault(node, node))
        flattened, done = [], {}
        for root in reversed(merged):
            root._gatherTables(flattened, None, done)
        flattened.reverse()
        local = 0
        for node in flattened:
            node.pos = local
            local += node.getDataLength()
        # getData checks every rewritten Offset16. Oversized individual trees
        # keep FontTools' valid layout or cause the caller to use its fallback.
        data = b''.join(node.getData() for node in flattened)
        for original, root in zip(roots, merged):
            original.pos = at+root.pos
        parts.append(data)
        at += len(data)
    head = b''.join(node.getData() for node in headers)
    return head+b''.join(parts) if len(head) == header_size else None
