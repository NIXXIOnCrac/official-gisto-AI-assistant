import sys, os, hashlib
sys.path.insert(0, os.path.dirname(__file__) + "/..")
for m in list(sys.modules):
    if "desktop" in m:
        del sys.modules[m]
print("=== On-disk key verification ===")
import src.desktop._built_keys as bk
from base64 import b64decode
X = 0xA7
def dec(blob):
    raw = bytes(ord(c) ^ X for c in blob)
    return b64decode(raw).decode("utf-8")
for n in ["_NOUS_B64_XOR", "_ELEVEN_B64_XOR", "_PLACES_B64_XOR", "_COMPOSIO_B64_XOR"]:
    print(f"  {n}: {dec(getattr(bk, n))!r} ({len(dec(getattr(bk, n)))} chars)")
h = hashlib.sha256(b"12041$").hexdigest()
print(f"  _PASSCODE_HASH: {bk._PASSCODE_HASH}")
print(f"  hash matches SHA-256 of '12041$': {bk._PASSCODE_HASH == h}")
print()
print("=== keys.py functions ===")
from src.desktop.keys import (
    nous_api_key, elevenlabs_api_key, google_places_api_key,
    composio_api_key, nous_base_url, PASSCODE_HASH,
)
print(f"  nous_api_key:   {nous_api_key()!r}")
print(f"  elevenlabs_key: {elevenlabs_api_key()!r}")
print(f"  places_key:     {google_places_api_key()!r}")
print(f"  composio_key:   {composio_api_key()!r}")
print(f"  base_url:       {nous_base_url()!r}")
print(f"  PASSCODE_HASH:  {PASSCODE_HASH}")
print(f"  hash match:     {PASSCODE_HASH == h}")
print()
print("=== keys.py is placeholder-only? ===")
src = open(os.path.join(os.path.dirname(__file__), "..", "src", "desktop", "keys.py")).read()
print(f"  Has REPLACE_ME: {'REPLACE_ME' in src}")
print(f"  REPLACE_ME count: {src.count('REPLACE_ME')}")
print()
print("=== EXE _built_keys check ===")
from PyInstaller.archive.readers import CArchiveReader
r = CArchiveReader(os.path.join(os.path.dirname(__file__), "..", "dist", "Gisto.exe"))
pyz = r.extract("PYZ.pyz")
idx = pyz.find(b"src.desktop._built_keys")
print(f"  _built_keys in EXE PYZ: {'YES' if idx >= 0 else 'NO'} (offset {idx})")
