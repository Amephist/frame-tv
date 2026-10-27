"""Rijksmuseum Linked Art APIs (CC0, no key).

Search only filters on fields (no free text), pages by cursor in fixed pages of 100 and returns bare IDs,
so each hit is resolved to its Linked Art record. A query searches titles, falling back to creators.
"""
import asyncio

import httpx

NAME = "rijks"
LABEL = "Rijksmuseum"
BASE = "https://data.rijksmuseum.nl/search/collection"
ENGLISH, DUTCH = "http://vocab.getty.edu/aat/300388277", "http://vocab.getty.edu/aat/300388256"
JSON = {"Accept": "application/ld+json"}

_pages: dict[tuple, dict] = {}  # search params -> {"ids": [...], "next": url | None, "total": n}
_objects: dict[str, dict | None] = {}


def _list(v) -> list:
    """JSON-LD gives a lone value instead of a one-item list."""
    return v if isinstance(v, list) else [] if v is None else [v]


def _name(names: list[dict]) -> str:
    """Prefer English, then Dutch, then whatever is first."""
    def lang(n):
        return {l.get("id") for l in _list(n.get("language"))}
    names = [n for n in names if n.get("content")]
    for want in (ENGLISH, DUTCH):
        for n in names:
            if want in lang(n):
                return n["content"]
    return names[0]["content"] if names else ""


def _parse(oid: str, o: dict) -> dict | None:
    image = None
    for s in _list(o.get("subject_of")):
        for c in _list(s.get("digitally_carried_by")):
            labels = {(ref.get("_label") or "").lower() for ref in _list(c.get("referred_to_by"))}
            for a in _list(c.get("access_point")):
                if "iiif.micr.io" in a.get("id", "") and "public domain" in labels:
                    image = a["id"].split("/full/")[0]
    if not image:
        return None
    produced = o.get("produced_by") or {}
    makers = [p for part in _list(produced.get("part")) for p in _list(part.get("carried_out_by"))]
    notation = _list(makers[0].get("notation")) if makers else []
    artist = next((n["@value"] for n in notation if n.get("@language") == "en"), notation[0]["@value"] if notation else "")
    titles = [n for n in _list(o.get("identified_by")) if n.get("type") == "Name"]
    timespan = (_list(produced.get("timespan")) or [{}])[0]
    return {
        "source": NAME,
        "id": oid,
        "title": _name(titles),
        "artist": artist,
        "date": _name(_list(timespan.get("identified_by"))),
        "thumb": f"{image}/full/!600,600/0/default.jpg",
        "image": f"{image}/full/!4096,4096/0/default.jpg",
        "width": None,
        "height": None,
    }


async def _object(client: httpx.AsyncClient, sem: asyncio.Semaphore, url: str) -> dict | None:
    oid = url.rsplit("/", 1)[-1]
    if oid in _objects:
        return _objects[oid]
    async with sem:
        r = await client.get(url, headers=JSON)
    if r.status_code != 200:
        return None
    _objects[oid] = _parse(oid, r.json())
    return _objects[oid]


async def _ids(client: httpx.AsyncClient, params: dict, upto: int) -> tuple[list[str], int]:
    """IDs for `params`, following cursors until at least `upto` are known (or results run out)."""
    key = tuple(sorted(params.items()))
    cache = _pages.setdefault(key, {"ids": [], "next": None, "total": None})
    while len(cache["ids"]) < upto and (cache["total"] is None or cache["next"]):
        r = await client.get(cache["next"] or BASE, params=None if cache["next"] else params, headers=JSON)
        r.raise_for_status()
        data = r.json()
        cache["ids"] += [it["id"] for it in data.get("orderedItems") or []]
        cache["total"] = data.get("partOf", {}).get("totalItems", 0)
        cache["next"] = (data.get("next") or {}).get("id")
    return cache["ids"], cache["total"]


async def search(client: httpx.AsyncClient, q: str, page: int, paintings: bool, size: int) -> tuple[list[dict], int]:
    base = {"imageAvailable": "true"}
    if paintings:
        base["type"] = "painting"
    upto = (page + 1) * size
    ids, total = await _ids(client, base | ({"title": q} if q else {}), upto)
    if q and not total:
        ids, total = await _ids(client, base | {"creator": q}, upto)
    sem = asyncio.Semaphore(6)
    objs = await asyncio.gather(*(_object(client, sem, url) for url in ids[page * size:upto]))
    return [o for o in objs if o], total
