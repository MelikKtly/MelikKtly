#!/usr/bin/env python3
"""
Turns a photo into assets/portrait.txt (the ASCII portrait on the hero card).

  pip install pillow numpy "rembg[cpu]"     # rembg is optional: removes the background
  python scripts/make_ascii_portrait.py assets/photo.jpg --crop 120,120,350,350

--crop is left,top,right,bottom in pixels of the source image (keep it square).
"""
import argparse
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter, ImageOps

RAMP = " .,:;-~=+*xo#%&@"
ap = argparse.ArgumentParser()
ap.add_argument("src")
ap.add_argument("--crop", default="")
ap.add_argument("--cols", type=int, default=112)
ap.add_argument("--rows", type=int, default=64)
ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "assets" / "portrait.txt"))
a = ap.parse_args()

im = Image.open(a.src).convert("RGBA")
try:
    from rembg import new_session, remove
    im = remove(im, session=new_session("u2net_human_seg"))
except ImportError:
    print("rembg not installed: keeping the background")
if a.crop:
    im = im.crop(tuple(int(v) for v in a.crop.split(",")))
alpha = im.split()[3]
g = ImageOps.grayscale(im.convert("RGB"))
g = ImageOps.equalize(g, mask=alpha.point(lambda v: 255 if v > 128 else 0))
g = g.filter(ImageFilter.UnsharpMask(2, 140, 2))
lum = np.asarray(g.resize((a.cols, a.rows), Image.LANCZOS), float) / 255
alp = np.asarray(alpha.resize((a.cols, a.rows), Image.LANCZOS), float) / 255
rows = []
for r in range(a.rows):
    line = "".join(" " if alp[r, c] < 0.35 else RAMP[max(1, round(lum[r, c] ** 0.9 * (len(RAMP) - 1)))]
                   for c in range(a.cols))
    rows.append(line.rstrip())
Path(a.out).write_text("\n".join(rows) + "\n", encoding="utf-8")
print(f"wrote {a.out}: {a.cols}x{a.rows}")
