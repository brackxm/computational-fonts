# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Text transport, including inert padding for the shaper's operation budget."""
PADDING = 64


def text(source):
    encoded = ''.join(chr(0xe100 + (ord(c) if ' ' <= c <= '~' else
                      32 if c in '\t\r\n' else 127)) for c in source)
    return '\ue000' + encoded + '\ue120' * (PADDING * (len(source) + 1)) + '\ue001'
