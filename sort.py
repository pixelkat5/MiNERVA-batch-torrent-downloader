#!/usr/bin/env python3
# Requirements: pip install requests
import os
import re
import glob
import hashlib
import time
import requests
import bencode
import sys

# config:
QBIT_HOST     = "http://localhost:8080"   # qBittorrent WebUI address
QBIT_USER     = "pixel"                   # WebUI username
QBIT_PASS     = "minerva"                 # WebUI password

TORRENT_DIR   = r"C:\Users\Greg\Downloads\MiNERVA-batch-torrent-downloader\used torrents"
SAVE_PATH     = r"F:\Torrents\MiNERVA"
# change if you want to.
CATEGORY      = "MiNERVA"
ADD_PAUSED    = False
ENGLISH_ONLY  = True

API = f"{QBIT_HOST}/api/v2"

_ENGLISH_REGIONS = {
    "usa", "europe", "uk", "australia", "canada", "world", "global",
}
_NON_ENGLISH_REGIONS = {
    "japan", "korea", "china", "taiwan", "brazil", "france", "germany",
    "italy", "spain", "russia", "netherlands", "sweden", "asia", "scandinavia",
}
_ALL_REGIONS = _ENGLISH_REGIONS | _NON_ENGLISH_REGIONS


def _parens_in_name(name: str) -> set[str]:
    """Return all (Tag) values in a filename stem, lowercased."""
    return {m.group(1).lower() for m in re.finditer(r"\(([^)]+)\)", name)}


def passes_region_filter(torrent_path: str) -> bool:
    """Return True if this torrent should be added."""
    if not ENGLISH_ONLY:
        return True

    stem = os.path.splitext(os.path.basename(torrent_path))[0]
    tags = _parens_in_name(stem)

    # World / Global -> always English
    if tags & {"world", "global"}:
        return True

    # Multi-lang tag containing "en" e.g. (En,Fr,De) -> has English
    for tag in tags:
        parts = {p.strip().lower() for p in tag.split(",")}
        if "en" in parts:
            return True

    # Check for known region tags
    known_hits = tags & _ALL_REGIONS
    if not known_hits:
        return True

    return bool(known_hits & _ENGLISH_REGIONS)


def login(session):
    r = session.post(f"{API}/auth/login", data={
        "username": QBIT_USER,
        "password": QBIT_PASS,
    })
    if r.text != "Ok.":
        print(f"[ERROR] Login failed: {r.text}")
        sys.exit(1)
    print("[OK] Logged in to qBittorrent.")


def get_torrent_hash(torrent_path):
    with open(torrent_path, "rb") as f:
        data = bencode.decode(f.read())
    info_encoded = bencode.encode(data["info"])
    return hashlib.sha1(info_encoded).hexdigest()


def display_name_from_filename(torrent_path):
    stem = os.path.splitext(os.path.basename(torrent_path))[0]
    stem = stem.replace("_", " ")
    for prefix in ("Minerva Myrient - ", "Minerva Myrient"):
        if stem.startswith(prefix):
            stem = stem[len(prefix):]
            break
    return stem.strip()


def rename_torrent(session, info_hash, new_name, filename):
    r = session.post(f"{API}/torrents/rename", data={
        "hash": info_hash,
        "name": new_name,
    })
    if r.status_code == 200:
        print(f"  [+] Renamed to: {new_name}")
    else:
        print(f"  [!] Rename failed for {filename}: {r.text}")


def add_torrent(session, torrent_path):
    filename  = os.path.basename(torrent_path)
    info_hash = get_torrent_hash(torrent_path)
    new_name  = display_name_from_filename(torrent_path)

    # Check if in qb if so-->> rename
    check = session.get(f"{API}/torrents/properties", params={"hash": info_hash})
    if check.status_code == 200:
        print(f"  [~] Already added, renaming: {filename}")
        rename_torrent(session, info_hash, new_name, filename)
        return

    with open(torrent_path, "rb") as f:
        torrent_data = f.read()

    data = {
        "savepath": SAVE_PATH,
        "paused":   "true" if ADD_PAUSED else "false",
    }
    if CATEGORY:
        data["category"] = CATEGORY

    r = session.post(
        f"{API}/torrents/add",
        files={"torrents": (filename, torrent_data, "application/x-bittorrent")},
        data=data,
    )

    if r.status_code != 200 or "Fails" in r.text:
        print(f"  [!] Failed to add ({r.text}): {filename}")
        return

    # Poll until qBit has reged torrents
    for _ in range(20):
        time.sleep(0.5)
        check = session.get(f"{API}/torrents/properties", params={"hash": info_hash})
        if check.status_code == 200:
            break
    else:
        print(f"  [!] Added but rename failed (never appeared): {filename}")
        return

    rename_torrent(session, info_hash, new_name, filename)


def main():
    pattern  = os.path.join(TORRENT_DIR, "*.torrent")
    torrents = sorted(glob.glob(pattern))

    if not torrents:
        print(f"[ERROR] No .torrent files found in: {TORRENT_DIR}")
        sys.exit(1)

    if ENGLISH_ONLY:
        wanted  = [t for t in torrents if     passes_region_filter(t)]
        skipped = [t for t in torrents if not passes_region_filter(t)]
        print(f"Found {len(torrents)} torrent(s) — {len(wanted)} pass English filter, {len(skipped)} skipped.")
    else:
        wanted  = torrents
        skipped = []
        print(f"Found {len(torrents)} torrent(s) in {TORRENT_DIR} (no region filter)")

    print(f"Save path: {SAVE_PATH}\\Minerva_Myrient\\")
    print()

    session = requests.Session()
    login(session)
    for t in wanted:
        add_torrent(session, t)

    if skipped:
        print()
        print(f"Skipped ({len(skipped)} non-English torrents):")
        for t in skipped:
            print(f"  - {os.path.basename(t)}")

    print()
    print("Done.")


if __name__ == "__main__":
    main()