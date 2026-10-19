# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Bond clearance for font label bounds, including the painted stroke width."""


def label_clearance(bounds, direction, offset=(0,0), gap=8, stroke_width=9):
    """Distance from a stroke's offset origin to the padded label rectangle."""
    padding=gap+stroke_width/2
    limits=[]
    for low,high,component,origin in zip(bounds[:2],bounds[2:],direction,offset):
        if component>1e-9:
            limits.append((high+padding-origin)/component)
        elif component < -1e-9:
            limits.append((low-padding-origin)/component)
    return max(0,min(limits))
