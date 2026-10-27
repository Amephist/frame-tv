"""SMK, National Gallery of Denmark, Open API (public-domain works are CC0)."""
import httpx

NAME = "smk"
LABEL = "SMK (Denmark)"
BASE = "https://api.smk.dk/api/v1/art/search/"


def _title(a: dict) -> str:
    titles = a.get("titles") or []
    english = [t for t in titles if t.get("language") == "engelsk"]
    return (english or titles or [{}])[0].get("title", "")


async def search(client: httpx.AsyncClient, q: str, page: int, paintings: bool, size: int) -> tuple[list[dict], int]:
    filters = ["[has_image:true]", "[public_domain:true]"]
    if paintings:
        filters.append("[object_names:maleri]")  # facet values are Danish
    params = {"keys": q or "*", "filters": ",".join(filters), "offset": page * size, "rows": size}
    r = await client.get(BASE, params=params)
    r.raise_for_status()
    data = r.json()
    results = []
    for a in data.get("items") or []:
        iiif = a.get("image_iiif_id")
        if not iiif:
            continue
        creators = a.get("production") or []
        dates = a.get("production_date") or []
        results.append({
            "source": NAME,
            "id": a["object_number"],
            "title": _title(a),
            "artist": creators[0].get("creator", "") if creators else "",
            "date": dates[0].get("period", "") if dates else "",
            "thumb": f"{iiif}/full/!600,600/0/default.jpg",
            # image_native is the full master (often 20+ MB); IIIF scales it server-side.
            "image": f"{iiif}/full/!4096,4096/0/default.jpg",
            "width": a.get("image_width"),
            "height": a.get("image_height"),
        })
    return results, data.get("found", 0)
