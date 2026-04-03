#!/usr/bin/env python3

# Requirements: pip install requests


import os
import glob
import hashlib
import time
import requests
import bencode
import sys

# config::
QBIT_HOST     = "http://localhost:8080"   # qBittorrent WebUI address
QBIT_USER     = "username"                   # WebUI username
QBIT_PASS     = "password"                 # WebUI password

# Folder containing .torrent files
TORRENT_DIR   = r"whereyourtorrentsarelocated"
SAVE_PATH     = r"whereyouwannastorethem"

# ima just set it to MiNERVA as the cat for now :P
# change if you want to.
CATEGORY      = "MiNERVA"

# Pause torrents on add? If True = add paused, Else False = start immediately
ADD_PAUSED    = False



API = f"{QBIT_HOST}/api/v2"
 
 
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
 
    # Check if in qb if so, rename
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
 
    print(f"Found {len(torrents)} torrent(s) in {TORRENT_DIR}")
    print(f"Save path: {SAVE_PATH}\\Minerva_Myrient\\")
    print()
 
    session = requests.Session()
    login(session)
 
    for t in torrents:
        add_torrent(session, t)
 
    print()
    print("Done.")
 
 
if __name__ == "__main__":
    main()
