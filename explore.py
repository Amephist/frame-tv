"""Exploration script: connect to the Frame TV and report what the Art Mode API can do.

Run this first — on first connect the TV will show an "Allow access?" popup,
accept it on the TV remote. A pairing token gets cached in token.txt so you
won't be prompted again.
"""
from samsungtvws import SamsungTVWS

from app.config import TOKEN_FILE, TV_IP

tv = SamsungTVWS(host=TV_IP, port=8002, token_file=TOKEN_FILE, name="frame-tv-explore")

print("== Art mode supported? ==")
print(tv.art().supported())

print("\n== Device info ==")
print(tv.art().get_device_info())

print("\n== API version ==")
print(tv.art().get_api_version())

print("\n== Current artwork ==")
print(tv.art().get_current())

print("\n== Available artwork (first 10) ==")
for item in tv.art().available()[:10]:
    print(item)

print("\n== Art mode on/off ==")
print(tv.art().get_artmode())

print("\n== Matte list ==")
print(tv.art().get_matte_list())

print("\n== Photo filter list ==")
print(tv.art().get_photo_filter_list())

print("\n== Slideshow status ==")
print(tv.art().get_slideshow_status())

print("\n== Auto-rotation status ==")
print(tv.art().get_auto_rotation_status())

print("\n== Brightness ==")
print(tv.art().get_brightness())
