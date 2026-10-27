import asyncio
import logging
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from samsungtvws.exceptions import ConnectionFailure, MessageError, ResponseError
from starlette.concurrency import run_in_threadpool
from websocket import WebSocketException

from . import db, imaging, tv
from .config import ROOT, USER_AGENT
from .sources import PAGE_SIZE, SOURCES

log = logging.getLogger("frame-tv")
app = FastAPI(title="frame-tv")
http = httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=60, follow_redirects=True)
STATIC = ROOT / "static"


class Aborted(Exception):
    pass


class UploadReq(BaseModel):
    source: str
    id: str
    title: str = ""
    artist: str = ""
    date: str = ""
    image: str
    mode: Literal["fill", "matte", "tv"] = "fill"
    crop: tuple[float, float, float, float] = (0, 0, 1, 1)  # x, y, w, h as fractions of the work
    border_color: str = "#000000"
    border: float = 0.1
    tv_matte: str = Field("modern_polar", pattern=r"^[a-z]+_[a-z]+$")  # TV-drawn matte, mode "tv"
    show: bool = True


@app.middleware("http")
async def revalidate_static(request: Request, call_next):
    # Browsers otherwise keep stale app.js/style.css for a while after an update.
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/")
async def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/sources")
async def sources():
    return [{"name": m.NAME, "label": m.LABEL} for m in SOURCES.values()]


@app.get("/api/search")
async def search(source: str, q: str = "", page: int = 0, paintings: bool = True):
    mod = SOURCES.get(source)
    if not mod:
        raise HTTPException(404, f"unknown source {source}")
    try:
        results, total = await mod.search(http, q, page, paintings, PAGE_SIZE)
    except httpx.HTTPError as e:
        raise HTTPException(502, f"{mod.LABEL}: {e}")
    for r in results:
        r["on_tv"] = db.find(r["source"], r["id"])
    return {"results": results, "total": total, "page": page, "page_size": PAGE_SIZE}


@app.get("/api/tv/status")
async def tv_status():
    s = await run_in_threadpool(tv.status)
    ours = db.all_by_content_id().values()
    s["app_uploads"] = {"count": len(ours), "bytes": sum(r["bytes"] or 0 for r in ours)}
    return s


@app.get("/api/tv/mattes")
async def tv_mattes():
    return await run_in_threadpool(tv.mattes)


@app.get("/api/tv/art")
async def tv_art():
    items = await run_in_threadpool(tv.my_photos)
    meta = db.all_by_content_id()
    for it in items:
        it["meta"] = meta.get(it["content_id"])
    return sorted(items, key=lambda it: it.get("image_date") or "", reverse=True)


@app.get("/api/tv/thumb/{content_id}")
async def tv_thumb(content_id: str):
    data = await run_in_threadpool(tv.thumbnail, content_id)
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "max-age=86400"})


@app.post("/api/tv/show/{content_id}")
async def tv_show(content_id: str):
    await run_in_threadpool(tv.show, content_id)
    return {"ok": True}


@app.post("/api/tv/artmode/{state}")
async def tv_artmode(state: str):
    await run_in_threadpool(tv.set_artmode, state == "on")
    return {"ok": True}


@app.delete("/api/tv/art/{content_id}")
async def tv_delete(content_id: str):
    await run_in_threadpool(tv.delete, content_id)
    db.remove(content_id)
    return {"ok": True}


@app.post("/api/tv/upload")
async def tv_upload(req: UploadReq, request: Request):
    """All or nothing: any failure or client abort after the TV accepts the image deletes it again.

    A work already on the TV is replaced: its previous copies are deleted once the new one is in place.
    """
    try:
        r = await http.get(req.image)
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise HTTPException(502, f"download failed: {e}")
    try:
        jpeg = await run_in_threadpool(imaging.prepare, r.content, req.mode, req.crop, req.border_color, req.border)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if await request.is_disconnected():
        raise Aborted()

    previous = db.find(req.source, req.id)
    # A drawn passepartout is part of the image; a TV matte on top would rescale it.
    matte = {"matte": req.border_color, "tv": req.tv_matte}.get(req.mode, "none")
    content_id = await run_in_threadpool(tv.upload, jpeg, matte if req.mode == "tv" else "none")
    try:
        if await request.is_disconnected():
            raise Aborted()
        if req.show:
            await run_in_threadpool(tv.show, content_id)
        if previous:
            await run_in_threadpool(tv.delete_many, previous)
        db.replace(previous, {
            "content_id": content_id, "source": req.source, "source_id": req.id,
            "title": req.title, "artist": req.artist, "date": req.date,
            "mode": req.mode, "matte": matte, "bytes": len(jpeg),
        })
    except BaseException:
        log.warning("upload of %s/%s failed after TV accepted it; deleting %s", req.source, req.id, content_id)
        # shield: a cancelled request must still finish the rollback
        try:
            await asyncio.shield(run_in_threadpool(tv.delete, content_id))
        except Exception:
            log.exception("rollback failed: %s is orphaned on the TV", content_id)
        raise
    return {"content_id": content_id, "bytes": len(jpeg)}


@app.exception_handler(Aborted)
async def aborted(_request, _exc):
    return Response(status_code=499)


async def tv_unreachable(_request, exc):
    return JSONResponse({"detail": f"TV: {exc or type(exc).__name__}"}, status_code=502)


for exc_type in (OSError, WebSocketException, ConnectionFailure, ResponseError, MessageError):
    app.add_exception_handler(exc_type, tv_unreachable)


app.mount("/static", StaticFiles(directory=STATIC), name="static")
