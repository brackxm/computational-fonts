# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Independent reference for the font's right-to-left polynomial hash."""

import unicodedata

MULTIPLIER = 257
MAX_INPUT = 4096
# Printable Latin through Latin Extended-A, plus common punctuation/currency.
# Soft hyphen is excluded because shapers treat it as default-ignorable.
CHARACTERS = ''.join(chr(c) for c in [*range(32, 127), *range(160, 173),
    *range(174, 384), 0x2010, 0x2011, 0x2012, 0x2013, 0x2014,
    0x2018, 0x2019, 0x201a, 0x201c, 0x201d, 0x201e, 0x2022, 0x2026, 0x20ac])
SEEDS = {char: index+1 for index, char in enumerate(CHARACTERS)}


def normalize(text):
    return unicodedata.normalize('NFC', text.replace('\r\n', ' ').replace('\r', ' ')
                                 .replace('\n', ' ').replace('\t', ' '))


def select_index(text, count):
    text = normalize(text)
    if not text.strip():
        raise ValueError('Type a word or paragraph.')
    if len(text) > MAX_INPUT:
        raise ValueError(f'Use at most {MAX_INPUT} characters.')
    result = 0
    for char in reversed(text):
        result = (SEEDS[char] + MULTIPLIER * result) % count
    return result
