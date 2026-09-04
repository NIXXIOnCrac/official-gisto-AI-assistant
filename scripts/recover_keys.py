"""Recover real key values from keys.py.bak (the old real-blob backup)."""
import re
from pathlib import Path
from base64 import b64decode

_XOR_KEY = 0xA7


def xor_decode(blob: str) -> str:
    try:
        raw = bytes((ord(c) ^ _XOR_KEY) for c in blob)
        return b64decode(raw).decode("utf-8")
    except Exception as e:
        return f"[ERR: {e}]"


bak = Path("src/desktop/keys.py.bak").read_text()
print("=== keys.py.bak — extracting real blobs ===\n")
keys_found: dict[str, str] = {}
for line in bak.splitlines():
    line = line.strip()
    for name_prefix in [
        "_NOUS_B64_XOR",
        "_ELEVEN_B64_XOR",
        "_PLACES_B64_XOR",
        "_COMPOSIO_B64_XOR",
    ]:
        if line.startswith(name_prefix + " ="):
            m = re.search(r'"([^"]+)"', line)
            if m:
                blob = m.group(1)
                decoded = xor_decode(blob)
                keys_found[name_prefix] = decoded
                print(f"{name_prefix}:")
                print(f"  blob   = {blob!r}")
                print(f"  decoded= {decoded!r}")
                print()

print("=== SUMMARY (env var exports) ===")
mapping = {
    "_NOUS_B64_XOR": "NOUS_API_KEY",
    "_ELEVEN_B64_XOR": "ELEVENLABS_API_KEY",
    "_PLACES_B64_XOR": "GOOGLE_PLACES_API_KEY",
    "_COMPOSIO_B64_XOR": "COMPOSIO_API_KEY",
}
for blob_name, env_name in mapping.items():
    val = keys_found.get(blob_name, "[NOT FOUND]")
    print(f'export {env_name}="{val}"')

print()
print('export GISTO_PASSCODE="12041$"')
print()
print(f"Recovered {len(keys_found)} of 4 key blobs.")
