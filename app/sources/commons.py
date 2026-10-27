"""Wikimedia Commons, restricted to public-domain and CC0 files.

Files tagged "digital representation of" (P6243) depict a specific artwork; that's our "paintings" filter.
Results can be photos of works rather than museum scans, and metadata is wiki markup.
"""
import html
import re

import httpx

NAME = "commons"
LABEL = "Wikimedia Commons"
BASE = "https://commons.wikimedia.org/w/api.php"
THUMB, IMAGE = 500, 3840  # Commons only serves standard thumbnail widths
FREE = ("public domain", "cc0", "pd")
_TAG = re.compile(r"<[^>]+>")
_HIDDEN = re.compile(r'<div style="display: none;">.*?</div>', re.S)


def _text(meta: dict, key: str) -> str:
    value = _HIDDEN.sub("", (meta.get(key) or {}).get("value", ""))
    return " ".join(html.unescape(_TAG.sub(" ", value)).split())


def _scaled(thumburl: str, width: int) -> str:
    return re.sub(r"/\d+px-", f"/{width}px-", thumburl, count=1)


async def search(client: httpx.AsyncClient, q: str, page: int, paintings: bool, size: int) -> tuple[list[dict], int]:
    terms = [q, "filetype:bitmap"]
    if paintings:
        terms.append("haswbstatement:P6243")
    params = {
        "action": "query", "format": "json", "formatversion": 2,
        "generator": "search", "gsrnamespace": 6, "gsrsearch": " ".join(t for t in terms if t),
        "gsrlimit": size, "gsroffset": page * size, "gsrinfo": "totalhits",
        "prop": "imageinfo", "iiprop": "url|size|extmetadata", "iiurlwidth": THUMB,
        "iiextmetadatafilter": "ObjectName|Artist|DateTimeOriginal|LicenseShortName",
    }
    r = await client.get(BASE, params=params)
    r.raise_for_status()
    data = r.json()
    query = data.get("query") or {}
    results = []
    for p in sorted(query.get("pages") or [], key=lambda p: p.get("index", 0)):
        info = (p.get("imageinfo") or [None])[0]
        if not info or not info.get("thumburl"):
            continue
        meta = info.get("extmetadata") or {}
        if not _text(meta, "LicenseShortName").lower().startswith(FREE):
            continue
        w, h = info["width"], info["height"]
        big = w > IMAGE
        results.append({
            "source": NAME,
            "id": str(p["pageid"]),
            "title": _text(meta, "ObjectName") or p["title"].removeprefix("File:").rsplit(".", 1)[0],
            "artist": _text(meta, "Artist"),
            "date": _text(meta, "DateTimeOriginal"),
            "thumb": info["thumburl"],
            # originals can be 100+ megapixels; the 3840px rendition is plenty for the panel
            "image": _scaled(info["thumburl"], IMAGE) if big else info["url"],
            "width": IMAGE if big else w,
            "height": round(h * IMAGE / w) if big else h,
        })
    return results, query.get("searchinfo", {}).get("totalhits", 0)
