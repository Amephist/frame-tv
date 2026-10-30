import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

TV_IP = os.environ.get("FRAME_TV_IP")
if not TV_IP:
    raise SystemExit("Set FRAME_TV_IP to your Frame TV's address, e.g. FRAME_TV_IP=192.168.1.50")
TOKEN_FILE = os.environ.get("FRAME_TV_TOKEN", str(ROOT / "token.txt"))
DATA_DIR = Path(os.environ.get("FRAME_TV_DATA", ROOT / "data"))
THUMB_DIR = DATA_DIR / "thumbs"
DB_PATH = DATA_DIR / "frame-tv.db"

# Category the TV files user-uploaded images under ("My Photos").
MY_PHOTOS = "MY-C0002"

USER_AGENT = "frame-tv/0.2 (+https://github.com/Amephist/frame-tv)"

DATA_DIR.mkdir(parents=True, exist_ok=True)
THUMB_DIR.mkdir(parents=True, exist_ok=True)
