"""Thin wrapper over samsungtvws Art Mode.

One call at a time: the TV's websocket misbehaves under concurrency. Every session has a hard
deadline; the library waits forever when the TV goes quiet, so a watchdog closes the socket.
"""
import re
import socket
import threading
from contextlib import contextmanager

from samsungtvws.art import SamsungTVArt

from .config import MY_PHOTOS, THUMB_DIR, TOKEN_FILE, TV_IP

PORT = 8002
QUICK, THUMBS, UPLOAD = 10, 20, 60  # seconds; working calls take ~1-2s, uploads a few more

_lock = threading.Lock()
_STORAGE_KEY = re.compile(r"storage|memory|capacity|space|free|disk|flash", re.I)


class TVTimeout(TimeoutError):
    pass


def _reachable() -> None:
    try:
        socket.create_connection((TV_IP, PORT), timeout=2).close()
    except OSError:
        raise TVTimeout("not reachable, is it asleep? Wake it with the remote") from None


@contextmanager
def session(deadline: float = QUICK):
    if not _lock.acquire(timeout=deadline):
        raise TVTimeout("busy with another request")
    try:
        _reachable()
        art = SamsungTVArt(host=TV_IP, port=PORT, token_file=TOKEN_FILE, timeout=deadline, name="frame-tv")
        expired = threading.Event()

        def kill():
            expired.set()
            art.close()

        watchdog = threading.Timer(deadline, kill)
        watchdog.start()
        try:
            yield art
        except Exception as e:
            if expired.is_set():
                raise TVTimeout(f"no answer within {deadline}s") from e
            raise
        finally:
            watchdog.cancel()
            art.close()
    finally:
        _lock.release()


def status() -> dict:
    with session() as art:
        info = art.get_device_info()
        return {
            "artmode": art.get_artmode(),
            "current": art.get_current(),
            "uploads_on_tv": len(art.available(MY_PHOTOS)),
            # Firmware-dependent; this 2022 Frame reports only tv_flash_size (GB total).
            "storage": {k: v for k, v in info.items() if _STORAGE_KEY.search(k)},
            "device_info": info,
        }


def my_photos() -> list[dict]:
    """List uploads and cache any missing thumbnails in one batch."""
    with session(THUMBS) as art:
        items = art.available(MY_PHOTOS)
        missing = [it["content_id"] for it in items if not _thumb_path(it["content_id"]).exists()]
        if missing:
            # This firmware answers get_thumbnail_list only; get_thumbnail never replies.
            for name, data in art.get_thumbnail_list(missing).items():
                (THUMB_DIR / name).write_bytes(bytes(data))
        return items


def _thumb_path(content_id: str):
    return THUMB_DIR / f"{content_id}.jpg"


def thumbnail(content_id: str) -> bytes:
    path = _thumb_path(content_id)
    if not path.exists():
        with session(THUMBS) as art:
            for name, data in art.get_thumbnail_list([content_id]).items():
                (THUMB_DIR / name).write_bytes(bytes(data))
    return path.read_bytes()


def upload(jpeg: bytes, matte: str) -> str:
    with session(UPLOAD) as art:
        return art.upload(jpeg, matte=matte, portrait_matte=matte, file_type="jpg")


def mattes() -> dict:
    with session() as art:
        return art.get_matte_list()


def show(content_id: str) -> None:
    with session() as art:
        art.select_image(content_id, category=MY_PHOTOS, show=True)


def set_artmode(on: bool) -> None:
    with session() as art:
        art.set_artmode(on)


def delete(content_id: str) -> None:
    delete_many([content_id])


def delete_many(content_ids: list[str]) -> None:
    with session() as art:
        art.delete_list(content_ids)
    for cid in content_ids:
        _thumb_path(cid).unlink(missing_ok=True)
