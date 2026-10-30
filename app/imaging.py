from io import BytesIO
from math import ceil

from PIL import Image, ImageCms, ImageColor, ImageOps

TV_W, TV_H = 3840, 2160
Image.MAX_IMAGE_PIXELS = 300_000_000  # museum masters are big, and trusted
TV_MODERN_MIN_RATIO = 1.5  # measured on this Frame: 3240x2160 shows with modern mattes, 3020x2160 doesn't
SRGB = ImageCms.createProfile("sRGB")


def ratio(data: bytes) -> float:
    w, h = Image.open(BytesIO(data)).size
    return w / h


def _srgb(im: Image.Image, icc: bytes | None) -> Image.Image:
    """Plain sRGB. Museum masters often carry Adobe RGB or ProPhoto profiles, which the TV ignores."""
    if im.mode not in ("RGB", "RGBA", "CMYK", "L"):
        im = im.convert("RGB")
    if icc:
        try:
            return ImageCms.profileToProfile(im, ImageCms.ImageCmsProfile(BytesIO(icc)), SRGB, outputMode="RGB")
        except (ImageCms.PyCMSError, OSError, ValueError):
            pass  # unreadable profile, or one that doesn't match the image's mode
    return im.convert("RGB")


def prepare(data: bytes, mode: str, crop: tuple[float, float, float, float] = (0, 0, 1, 1),
            border_color: str = "#000000", border: float = 0.1,
            size: tuple[int, int] = (TV_W, TV_H), quality: int = 95) -> bytes:
    """Return the JPEG to upload, cut to `crop` (x, y, w, h as fractions of the work) first.

    fill:  full panel 3840x2160 shown 1:1; a crop that isn't 16:9 is centered on black.
    matte: full panel with the work centered on a passepartout drawn into the image; `border` is
           the minimum margin as a fraction of panel height, `border_color` any CSS color.
    tv:    just the cropped work, fitted to the panel; the TV draws its own matte around it.
    `size` other than the panel's renders a scaled-down preview of the same result.
    """
    W, H = size
    x, y, w, h = (min(max(v, 0), 1) for v in crop)
    w, h = max(min(w, 1 - x), 0.01), max(min(h, 1 - y), 0.01)
    im = Image.open(BytesIO(data))
    icc = im.info.get("icc_profile")
    # JPEG: decode at reduced scale, still >= target once cropped (square covers EXIF rotation)
    im.draft("RGB", (ceil(W / min(w, h)),) * 2)
    im = ImageOps.exif_transpose(im)
    iw, ih = im.size
    im = _srgb(im.crop((round(x * iw), round(y * ih), round((x + w) * iw), round((y + h) * ih))), icc)

    if mode == "fill" and abs(im.width / im.height / (TV_W / TV_H) - 1) < 0.01:
        out = im.resize((W, H), Image.LANCZOS)
    elif mode == "tv":
        out = ImageOps.contain(im, (W, H), Image.LANCZOS)
    else:
        color = border_color if mode == "matte" else "#000000"
        margin = round(H * min(max(border, 0), 0.4)) if mode == "matte" else 0
        art = ImageOps.contain(im, (W - 2 * margin, H - 2 * margin), Image.LANCZOS)
        out = Image.new("RGB", (W, H), ImageColor.getrgb(color))
        out.paste(art, ((W - art.width) // 2, (H - art.height) // 2))

    buf = BytesIO()
    out.save(buf, "JPEG", quality=quality)
    return buf.getvalue()
