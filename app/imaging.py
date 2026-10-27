from io import BytesIO
from math import ceil

from PIL import Image, ImageColor, ImageOps

TV_W, TV_H = 3840, 2160
Image.MAX_IMAGE_PIXELS = 300_000_000  # museum masters are big, and trusted


def prepare(data: bytes, mode: str, crop: tuple[float, float, float, float] = (0, 0, 1, 1),
            border_color: str = "#000000", border: float = 0.1) -> bytes:
    """Return the JPEG to upload, cut to `crop` (x, y, w, h as fractions of the work) first.

    fill:  full panel 3840x2160 shown 1:1; a crop that isn't 16:9 is centered on black.
    matte: full panel with the work centered on a passepartout drawn into the image; `border` is
           the minimum margin as a fraction of panel height, `border_color` any CSS color.
    tv:    just the cropped work, fitted to the panel; the TV draws its own matte around it.
    """
    x, y, w, h = (min(max(v, 0), 1) for v in crop)
    w, h = max(min(w, 1 - x), 0.01), max(min(h, 1 - y), 0.01)
    im = Image.open(BytesIO(data))
    # JPEG: decode at reduced scale, still >= target once cropped (square covers EXIF rotation)
    im.draft("RGB", (ceil(TV_W / min(w, h)),) * 2)
    im = ImageOps.exif_transpose(im).convert("RGB")
    iw, ih = im.size
    im = im.crop((round(x * iw), round(y * ih), round((x + w) * iw), round((y + h) * ih)))

    if mode == "fill" and abs(im.width / im.height / (TV_W / TV_H) - 1) < 0.01:
        out = im.resize((TV_W, TV_H), Image.LANCZOS)
    elif mode == "tv":
        out = ImageOps.contain(im, (TV_W, TV_H), Image.LANCZOS)
    else:
        color = border_color if mode == "matte" else "#000000"
        margin = round(TV_H * min(max(border, 0), 0.4)) if mode == "matte" else 0
        art = ImageOps.contain(im, (TV_W - 2 * margin, TV_H - 2 * margin), Image.LANCZOS)
        out = Image.new("RGB", (TV_W, TV_H), ImageColor.getrgb(color))
        out.paste(art, ((TV_W - art.width) // 2, (TV_H - art.height) // 2))

    buf = BytesIO()
    out.save(buf, "JPEG", quality=95)
    return buf.getvalue()
