"""Handwritten-style order photo renderer (SPEC section 2)."""

from __future__ import annotations

import glob as _glob
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

WIDTH = 900

_FONT_CANDIDATES = [
    "C:/Windows/Fonts/Inkfree.ttf",
    "segoepr.ttf",
    "segoesc.ttf",
]


def _load_font(size: int):
    for candidate in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    for candidate in sorted(_glob.glob("/usr/share/fonts/**/DejaVuSans.ttf", recursive=True)):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default(size=28)


def _text_width(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def render_list(lines: list[str], path: Path, seed: int) -> None:
    """Render order lines as a handwritten-style list photo, 900 px wide PNG."""
    rng = random.Random(seed)
    path = Path(path)
    size = rng.randint(26, 32)
    fonts: dict[int, object] = {}

    def font_for(px: int):
        if px not in fonts:
            fonts[px] = _load_font(px)
        return fonts[px]

    base_font = font_for(size)
    margin = 44
    line_h = size + 20
    n = max(1, len(lines))
    height = margin * 2 + line_h * n + 12
    paper = (253, 251, 242)
    img = Image.new("RGB", (WIDTH, height), paper)
    draw = ImageDraw.Draw(img)
    for rule_y in range(margin // 2, height - 6, line_h):
        draw.line([(12, rule_y), (WIDTH - 12, rule_y)], fill=(168, 198, 232), width=1)
    y = margin
    for text in lines:
        cur = size
        cur_font = base_font
        while _text_width(draw, text, cur_font) > WIDTH - 2 * margin and cur > 18:
            cur -= 2
            cur_font = font_for(cur)
        strip = Image.new("RGBA", (WIDTH, 2 * line_h), (0, 0, 0, 0))
        sdraw = ImageDraw.Draw(strip)
        ink = (
            28 + rng.randint(-8, 8),
            38 + rng.randint(-8, 8),
            78 + rng.randint(-8, 8),
            235,
        )
        sdraw.text((24, 4), text, font=cur_font, fill=ink)
        strip = strip.rotate(rng.uniform(-1.5, 1.5), expand=True, resample=Image.BICUBIC)
        img.paste(strip, (margin - 24 + rng.randint(-3, 3), y - 6 + rng.randint(-3, 3)), strip)
        y += line_h
    img = img.rotate(rng.uniform(-2.0, 2.0), resample=Image.BICUBIC, fillcolor=paper)
    img = img.filter(ImageFilter.GaussianBlur(0.5))
    dots = ImageDraw.Draw(img)
    for _ in range(2500):
        x = rng.randint(0, WIDTH - 1)
        yy = rng.randint(0, img.height - 1)
        v = rng.randint(-10, 10)
        dots.point((x, yy), fill=(253 + v, 251 + v, 242 + v))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(path), "PNG")
