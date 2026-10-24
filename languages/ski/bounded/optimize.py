# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Remove unreachable GSUB templates after allocating the finite schedule.

Adapted from agent-work-2's bounded/optimize_v42.py. Use FontTools' lookup
closure/remapping directly: no glyphs, features, GDEF sets or outlines are
subsetted. Contextual helper lookups remain reachable through their callers.
"""
from fontTools import subset  # Registers prune_lookups on the GSUB table class.
from fontTools.ttLib import newTable


def prune_lookups(font):
    table = font['GSUB']
    before = table.table.LookupList.LookupCount
    # Scheduled lookup copies share contextual subtables in memory. Remapping
    # those shared objects repeatedly corrupts nested lookup indices. The old
    # file-based optimizer implicitly broke these aliases by loading a saved
    # font; perform that round trip for GSUB alone before applying its closure.
    loaded = newTable('GSUB')
    loaded.decompile(table.compile(font), font)
    loaded.prune_lookups()
    font['GSUB'] = loaded
    return before - loaded.table.LookupList.LookupCount
