#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Franz Schöning, https://www.schoning.com
"""Render captured terminal text as a terminal-style PNG (the screenshots in docs/rawfront/images).

Input: a text file with the exact stdout/stderr of real runs against the radio. Lines starting with "$ " are
shown as typed commands. A line rewritten with carriage returns (a progress counter) shows its last state.
Nothing else is changed; where lines were left out, the caption in the docs says so.

  python term2png.py capture.txt out.png --title "rawcap: raw ADC stream"
Needs Pillow.
"""

import argparse
import textwrap

from PIL import Image, ImageDraw, ImageFont

BG, BAR, FG, PROMPT, CMD, DIM = (30, 30, 30), (55, 55, 58), (212, 212, 212), (106, 196, 104), (255, 255, 255), (150, 150, 150)
FONTS = ["C:/Windows/Fonts/consola.ttf", "C:/Windows/Fonts/CascadiaMono.ttf", "DejaVuSansMono.ttf"]


def load_font(size):
    for f in FONTS:
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("text")
    ap.add_argument("png")
    ap.add_argument("--title", default="terminal")
    ap.add_argument("--cols", type=int, default=120, help="wrap longer lines")
    ap.add_argument("--size", type=int, default=15)
    args = ap.parse_args()

    raw = open(args.text, encoding="utf-8", errors="replace", newline="").read().replace("\r\n", "\n").rstrip("\n").split("\n")
    lines = []
    for l in raw:
        l = l.rstrip("\r").split("\r")[-1].replace("\t", "    ")     # a progress line shows its last state
        wrapped = textwrap.wrap(l, args.cols, replace_whitespace=False, drop_whitespace=False) or [""]
        lines += [(wrapped[0], l.startswith("$ "))] + [(w, False) for w in wrapped[1:]]

    font = load_font(args.size)
    cw = font.getlength("M")
    lh = int(args.size * 1.35)
    cols = min(args.cols, max(len(t) for t, _ in lines))
    pad, bar = 16, 30
    w = int(pad * 2 + cw * max(cols, 40)) + 1
    h = bar + pad * 2 + lh * len(lines)
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w, bar], fill=BAR)
    for i, c in enumerate([(237, 106, 94), (245, 191, 79), (98, 197, 84)]):
        d.ellipse([12 + i * 20, 9, 24 + i * 20, 21], fill=c)
    tf = load_font(args.size - 2)
    tw = d.textlength(args.title, font=tf)
    d.text(((w - tw) / 2, 7), args.title, font=tf, fill=DIM)
    y = bar + pad
    for text, is_cmd in lines:
        if is_cmd:
            d.text((pad, y), "$", font=font, fill=PROMPT)
            d.text((pad + 2 * cw, y), text[2:], font=font, fill=CMD)
        else:
            d.text((pad, y), text, font=font, fill=FG)
        y += lh
    img.save(args.png, optimize=True)


if __name__ == "__main__":
    main()
