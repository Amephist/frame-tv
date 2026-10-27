"""Victoria and Albert Museum Collections API v2 (images free for non-commercial use)."""
import httpx

NAME = "vam"
LABEL = "V&A"
BASE = "https://api.vam.ac.uk/v2/objects/search"
PAINTINGS = "THES48917"  # "Paintings" category; object_type is free text ("Oil painting", ...)


async def search(client: httpx.AsyncClient, q: str, page: int, paintings: bool, size: int) -> tuple[list[dict], int]:
    params = {"q": q, "images_exist": "true", "page": page + 1, "page_size": size}
    if paintings:
        params["id_category"] = PAINTINGS
    r = await client.get(BASE, params=params)
    r.raise_for_status()
    data = r.json()
    results = []
    for a in data.get("records") or []:
        iiif = (a.get("_images") or {}).get("_iiif_image_base_url")
        if not iiif:
            continue
        results.append({
            "source": NAME,
            "id": a["systemNumber"],
            "title": a.get("_primaryTitle") or a.get("objectType") or "",
            "artist": (a.get("_primaryMaker") or {}).get("name", ""),
            "date": a.get("_primaryDate") or "",
            "thumb": f"{iiif}full/!600,600/0/default.jpg",
            "image": f"{iiif}full/full/0/default.jpg",  # V&A masters top out around 2-3k px
            "width": None,
            "height": None,
        })
    return results, data.get("info", {}).get("record_count", 0)
