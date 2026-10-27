"""Museum adapters. Each exposes NAME, LABEL and `async search(client, q, page, paintings) -> (list[dict], total)`.

Result dicts: source, id, title, artist, date, thumb, image, width, height (width/height may be None).
"""
from . import cleveland, commons, met, rijks, smk, vam

SOURCES = {m.NAME: m for m in (met, cleveland, rijks, smk, vam, commons)}
PAGE_SIZE = 24
