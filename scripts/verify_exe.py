"""Verify EXE bundles correct _built_keys.py, then smoke test, then report git status."""

from __future__ import annotations

import sys
import os
import hashlib
import subprocess

sys.path.insert(0, os.path.dirname(__file__) + "/..")

# ------------------------------------------------------------------
# 1. Extract PYZ.pyz from EXE and check _built_keys is inside
# ------------------------------------------------------------------
print("=" * 60)
print("1. Checking EXE for _built_keys.pyc via PyInstaller CArchiveReader")
print("=" * 60)

from PyInstaller.archive.readers import CArchiveReader

exe_path = os.path.join(os.path.dirname(__file__), "..", "dist", "Gisto.exe")
r = CArchiveReader(exe_path)
toc = r.toc

# Search EXE TOC for any desktop keys-related entry
found = False
for name in toc:
    if "_built_keys" in name or ("keys" in name.lower() and "desktop" in name.lower()):
        print(f"  FOUND in EXE TOC: {name}: {toc[name]}")
        found = True

if not found:
    # Also check via the PYZ index
    print("  Not in main TOC — checking via PYZ.pyz extraction...")
    pyz_data = r.extract("PYZ.pyz")
    # PyInstaller PYZ v2: magic(4) + zlib(data)
    import zlib
    try:
        data = zlib.decompress(pyz_data[4:])
    except Exception:
        # Try with wbits
        for wbits in [15, -15, 47, 31]:
            try:
                data = zlib.decompress(pyz_data[4:], wbits)
                break
            except Exception:
                pass
        else:
            print("  ERROR: Cannot decompress PYZ.pyz")
            # Fallback: search raw
            idx = pyz_data.find(b"_built_keys")
            if idx >= 0:
                print(f"  Found '_built_keys' string in raw PYZ at offset {idx}")
                found = True
            else:
                print("  ERROR: _built_keys NOT found in EXE at all")
                print("  The EXE will fail at runtime when keys.py tries 'from ._built_keys import'")
                sys.exit(1)
            sys.exit(0)

    # Parse PYZ TOC
    import marshal
    toc_obj = marshal.loads(data[:8000])
    if isinstance(toc_obj, dict):
        for name in toc_obj:
            if "_built_keys" in name:
                print(f"  FOUND in PYZ TOC: {name!r} -> {toc_obj[name]}")
                found = True
    if not found:
        print("  ERROR: _built_keys NOT found in PYZ TOC either")
        sys.exit(1)

print("  _built_keys IS bundled in the EXE: OK")
print()

# Parse PYZ TOC (marshalled dict at start of decompressed data)
try:
    toc_obj = marshal.loads(data[:5000])
    if isinstance(toc_obj, dict):
        print(f"TOC is a dict with {len(toc_obj)} entries")
        for name in toc_obj:
            if "_built_keys" in name or ("keys" in name.lower() and name.endswith(".pyc")):
                print(f"  TOC entry: {name!r} -> {toc_obj[name]}")
    else:
        print(f"TOC is {type(toc_obj).__name__}, not a dict")
        # Try scanning
        idx = data.find(b"_built_keys")
        if idx >= 0:
            print(f"Found '_built_keys' in decompressed data at offset {idx}")
except Exception as e:
    print(f"Failed to parse TOC: {e}")
    # Scan raw
    idx = data.find(b"_built_keys")
    if idx >= 0:
        print(f"Found '_built_keys' string at offset {idx} in decompressed data")
        print(f"Context: {data[max(0,idx-20):idx+60]!r}")

# ------------------------------------------------------------------
# 2. Look for _built_keys.pyc in the EXE's main TOC
# ------------------------------------------------------------------
print()
print("=" * 60)
print("2. Searching EXE main TOC for _built_keys / keys")
print("=" * 60)

for name in toc:
    if "_built_keys" in name or "keys" in name.lower():
        print(f"  {name}: {toc[name]}")

# ------------------------------------------------------------------
# 4. Verify _built_keys.py on disk is correct
# ------------------------------------------------------------------
print()
print("=" * 60)
print("4. Verifying on-disk _built_keys.py decodes correctly")
print("=" * 60)

for m in list(sys.modules):
    if "desktop" in m:
        del sys.modules[m]

import src.desktop._built_keys as bk
from base64 import b64decode

_XOR = 0xA7

def decode_blob(blob: str) -> str:
    return b64decode(bytes(ord(c) ^ _XOR for c in blob)).decode("utf-8")

blobs = {
    "_NOUS_B64_XOR": bk._NOUS_B64_XOR,
    "_ELEVEN_B64_XOR": bk._ELEVEN_B64_XOR,
    "_PLACES_B64_XOR": bk._PLACES_B64_XOR,
    "_COMPOSIO_B64_XOR": bk._COMPOSIO_B64_XOR,
}

for name, blob in blobs.items():
    decoded = decode_blob(blob)
    print(f"  {name}: {decoded!r}  ({len(decoded)} chars)")

expected_hash = hashlib.sha256(b"12041$").hexdigest()
hash_ok = bk._PASSCODE_HASH == expected_hash
print(f"  _PASSCODE_HASH: {bk._PASSCODE_HASH}")
print(f"  hash match (SHA-256 of '12041$'): {hash_ok}")

# ------------------------------------------------------------------
# 5. Verify keys.py functions return correct values
# ------------------------------------------------------------------
print()
print("=" * 60)
print("5. Verifying keys.py functions")
print("=" * 60)

from src.desktop.keys import (
    nous_api_key,
    elevenlabs_api_key,
    google_places_api_key,
    composio_api_key,
    nous_base_url,
    PASSCODE_HASH,
)

print(f"  nous_api_key():       {nous_api_key()!r}")
print(f"  elevenlabs_api_key(): {elevenlabs_api_key()!r}")
print(f"  google_places_api_key(): {google_places_api_key()!r}")
print(f"  composio_api_key():   {composio_api_key()!r}")
print(f"  nous_base_url():      {nous_base_url()!r}")
print(f"  PASSCODE_HASH:        {PASSCODE_HASH!r}")

# Verify they match the decoded blobs
assert nous_api_key() == decode_blob(bk._NOUS_B64_XOR), "NOUS mismatch!"
assert elevenlabs_api_key() == decode_blob(bk._ELEVEN_B64_XOR), "ELEVEN mismatch!"
assert google_places_api_key() == decode_blob(bk._PLACES_B64_XOR), "PLACES mismatch!"
assert composio_api_key() == decode_blob(bk._COMPOSIO_B64_XOR), "COMPOSIO mismatch!"
print("  All keys.py functions match decoded blobs: OK")

# ------------------------------------------------------------------
# 6. Run smoke test
# ------------------------------------------------------------------
print()
print("=" * 60)
print("6. Running smoke_test.py")
print("=" * 60)

os.chdir(os.path.join(os.path.dirname(__file__), ".."))
result = subprocess.run(
    [sys.executable, "scripts/smoke_test.py"],
    capture_output=True,
    text=True,
    timeout=30,
)
print(f"  exit code: {result.returncode}")
print(f"  stdout (last 500 chars):")
print(result.stdout[-500:])
if result.stderr:
    print(f"  stderr (last 500 chars):")
    print(result.stderr[-500:])
if result.returncode == 0:
    print("  PASS (exit 0 = clean exit)")
elif result.returncode == 124:
    print("  PASS (exit 124 = killed by timeout = no crash)")
else:
    print(f"  FAIL (exit {result.returncode} = crashed)")

# ------------------------------------------------------------------
# 7. Git status
# ------------------------------------------------------------------
print()
print("=" * 60)
print("7. Git status")
print("=" * 60)

result = subprocess.run(
    ["git", "status", "--short"],
    capture_output=True,
    text=True,
)
print(result.stdout)

print()
print("=" * 60)
print("VERIFICATION COMPLETE")
print("=" * 60)
