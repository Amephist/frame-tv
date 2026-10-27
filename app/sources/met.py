"""The Met Collection API (v1.1 search, CC0 open access)."""
import asyncio

import httpx

NAME = "met"
LABEL = "The Met"
BASE = "https://collectionapi.metmuseum.org/public/collection"


_objects: dict[int, dict | None] = {}  # object lookups are the bulk of traffic; works don't change


async def _get(client: httpx.AsyncClient, url: str, **kw) -> httpx.Response:
    """The Met's CDN (Imperva) answers bursts with 403/429; back off once before giving up."""
    r = await client.get(url, **kw)
    if r.status_code in (403, 429):
        await asyncio.sleep(2)
        r = await client.get(url, **kw)
    return r


async def _object(client: httpx.AsyncClient, sem: asyncio.Semaphore, oid: int) -> dict | None:
    if oid in _objects:
        return _objects[oid]
    async with sem:
        r = await _get(client, f"{BASE}/v1/objects/{oid}")
    if r.status_code != 200:
        return None  # not cached: a block is temporary
    _objects[oid] = _parse(r.json())
    return _objects[oid]


def _parse(o: dict) -> dict | None:
    if not (o.get("isPublicDomain") and o.get("primaryImage")):
        return None
    return {
        "source": NAME,
        "id": str(o["objectID"]),
        "title": o.get("title") or "",
        "artist": o.get("artistDisplayName") or "",
        "date": o.get("objectDate") or "",
        "thumb": o.get("primaryImageSmall") or o["primaryImage"],
        "image": o["primaryImage"],
        "width": None,
        "height": None,
    }


async def search(client: httpx.AsyncClient, q: str, page: int, paintings: bool, size: int) -> tuple[list[dict], int]:
    params = {"q": q or "*", "hasImages": "true", "isPublicDomain": "true", "offset": page * size, "limit": size}
    if paintings:
        params["medium"] = "Paintings"
    r = await _get(client, f"{BASE}/v1.1/search", params=params)
    if r.status_code in (403, 429):
        raise httpx.HTTPStatusError("rate-limited by the museum's servers, try again in a minute", request=r.request, response=r)
    r.raise_for_status()
    data = r.json()
    sem = asyncio.Semaphore(4)
    objs = await asyncio.gather(*(_object(client, sem, oid) for oid in data.get("objectIDs") or []))
    return [o for o in objs if o], data.get("total", 0)
