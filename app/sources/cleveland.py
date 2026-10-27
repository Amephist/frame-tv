"""Cleveland Museum of Art Open Access API (CC0)."""
import httpx

NAME = "cleveland"
LABEL = "Cleveland Museum of Art"
BASE = "https://openaccess-api.clevelandart.org/api/artworks/"


def _artist(a: dict) -> str:
    creators = a.get("creators") or []
    return creators[0].get("description", "") if creators else ""


async def search(client: httpx.AsyncClient, q: str, page: int, paintings: bool, size: int) -> tuple[list[dict], int]:
    params = {
        "q": q,
        "cc0": 1,
        "has_image": 1,
        "skip": page * size,
        "limit": size,
        "fields": "id,title,creators,creation_date,images",
    }
    if paintings:
        params["type"] = "Painting"
    r = await client.get(BASE, params=params)
    r.raise_for_status()
    data = r.json()
    results = []
    for a in data.get("data", []):
        images = a.get("images") or {}
        web, best = images.get("web"), images.get("print") or images.get("web")
        if not best:
            continue
        results.append({
            "source": NAME,
            "id": str(a["id"]),
            "title": a.get("title") or "",
            "artist": _artist(a),
            "date": a.get("creation_date") or "",
            "thumb": (web or best)["url"],
            # "full" is a multi-hundred-MB TIFF; "print" JPEG (~3k px) suits a 4K panel.
            "image": best["url"],
            "width": int(best["width"]),
            "height": int(best["height"]),
        })
    return results, data.get("info", {}).get("total", 0)
