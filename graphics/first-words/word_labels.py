# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Expand explicit picture labels and reject ambiguous input spellings."""

import re


def expand_labels(labels, drawing_id):
    values = set()
    for label in labels:
        if not isinstance(label, str) or not re.fullmatch(r'[a-z]+(?:[ -][a-z]+)*', label):
            raise ValueError(f"Invalid label for {drawing_id}: {label!r}")
        values.add(label)
        if ' ' in label:
            values.update((label.replace(' ', '-'), label.replace(' ', ''),
                           label.replace(' ', '\u00a0')))
    return sorted(values)


def spellings(drawing):
    return expand_labels([drawing['label'], *drawing.get('aliases', [])], drawing['id'])


def plural_spellings(drawing):
    return expand_labels(drawing.get('plurals', []), drawing['id'])


def validate_labels(drawings):
    owners = {}
    for drawing in drawings:
        labels = {drawing['label'], *drawing.get('aliases', [])}
        if not set(drawing.get('plurals', [])) <= labels:
            raise ValueError(f"Plural labels must be existing labels for {drawing['id']}")
        for text in spellings(drawing):
            previous = owners.setdefault(text, drawing['id'])
            if previous != drawing['id']:
                raise ValueError(f'Ambiguous label {text!r}: {previous} and {drawing["id"]}')
    return owners
