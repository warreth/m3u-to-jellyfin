#!/usr/bin/env python3
import os
import requests
import re
import urllib.parse
import sys
import time
import difflib
import json
import argparse

# ================= CONFIGURATION =================
JELLYFIN_URL = "http://localhost:8096"
API_KEY = ""
USER_ID = ""
M3U_FOLDER = ""
FUZZY_THRESHOLD = 0.85 # 85% similarity required
# =================================================

parser = argparse.ArgumentParser()
parser.add_argument('-u', '--url', default=JELLYFIN_URL, type=str)
parser.add_argument('-k', '--api-key', default=API_KEY, type=str)
parser.add_argument('-i', '--user-id', default=USER_ID, type=str)
parser.add_argument('-t', '--threshold', default=FUZZY_THRESHOLD, type=float)
parser.add_argument('-f', '--m3u-folder', default=M3U_FOLDER, type=str)

args = parser.parse_args()
[JELLYFIN_URL, API_KEY, USER_ID, FUZZY_THRESHOLD, M3U_FOLDER] = list(vars(args).values())

session = requests.Session()
session.headers.update({"X-Emby-Token": API_KEY, "Content-Type": "application/json"})

def clean_text(text):
    """
    Creates a 'search key'.
    1. Decodes URL
    2. Removes brackets [] and parentheses () content
    3. Removes junk words
    4. Removes leading 'the'
    5. Returns only alphanumeric characters
    """
    if not text: return ""
    text = urllib.parse.unquote(text).lower()

    # Remove youtube brackets [id]
    text = re.sub(r'\[.*?\]', '', text)
    # Remove parentheses content (remix info, etc)
    text = re.sub(r'\(.*?\)', '', text)

    # Remove junk words
    junk = ["official", "video", "audio", "lyrics", "visualiser", "visualizer", "hd", "4k", "mv", "soundtrack", "topic"]
    for word in junk:
        text = text.replace(word, "")

    # Remove non-alphanumeric (keep letters and numbers only)
    # This turns "B.o.B" into "bob", "Fun." into "fun"
    text = re.sub(r'[^a-z0-9]', '', text)

    # Remove leading "the" (The Kooks -> kooks)
    if text.startswith("the"):
        text = text[3:]

    return text

def fetch_library_index():
    print("⏳ Downloading library index...")
    start = time.time()

    params = {"IncludeItemTypes": "Audio", "Recursive": "true", "Fields": "Name,Artists", "UserId": USER_ID}

    try:
        r = session.get(f"{JELLYFIN_URL}/Items", params=params)
        items = r.json().get("Items", [])
    except Exception as e:
        print(f"❌ API Error: {e}")
        sys.exit(1)

    print(f"   Fetched {len(items)} items in {round(time.time() - start, 2)}s. Building Index...")

    # We store keys pointing to IDs
    # We also keep a list of keys for Fuzzy matching
    index_map = {}

    for item in items:
        item_id = item["Id"]
        name = item["Name"]
        artists = item.get("Artists", [])

        # 1. Title Only Key
        t_key = clean_text(name)
        if t_key: index_map[t_key] = item_id

        # 2. Artist + Title Key
        for artist in artists:
            a_key = clean_text(artist)
            if a_key and t_key:
                full_key = a_key + t_key
                index_map[full_key] = item_id

    print(f"✅ Index ready ({len(index_map)} keys).")
    return index_map

def find_fuzzy_match(search_key, index_keys):
    # Returns the best match if score > threshold
    matches = difflib.get_close_matches(search_key, index_keys, n=1, cutoff=FUZZY_THRESHOLD)
    if matches:
        return matches[0]
    return None

def find_in_index(filename, index_map):
    # 1. Check file extension for non-audio
    ext = os.path.splitext(filename)[1].lower()
    if ext in ['.webp', '.jpg', '.png', '.jpeg', '.nfo']:
        return None, "Not an audio file"

    # 2. Split filename (Artist - Title)
    # Splits on ' - ', ' | ', ' : ', ' – '
    parts = re.split(r' - | \| | ｜ | : | – ', filename)

    candidates = []

    # Candidate A: The Title (Last part of split)
    if len(parts) > 1:
        candidates.append(parts[-1])

    # Candidate B: The Full Filename
    candidates.append(os.path.splitext(filename)[0])

    for raw_string in candidates:
        # Step 1: Clean
        key = clean_text(raw_string)
        if not key: continue

        # Step 2: Exact Match
        if key in index_map:
            return index_map[key], "Exact Match"

        # Step 3: Fuzzy Match (Slower, but catches typos)
        # Only do this if key is long enough to be meaningful
        if len(key) > 4:
            fuzzy_key = find_fuzzy_match(key, index_map.keys())
            if fuzzy_key:
                return index_map[fuzzy_key], f"Fuzzy Match ({fuzzy_key})"

    return None, "Missing"

def get_or_create_playlist(name):
    try:
        r = session.get(f"{JELLYFIN_URL}/Users/{USER_ID}/Items",
                        params={"searchTerm": name, "IncludeItemTypes": "Playlist", "Recursive": "true"})
        data = r.json()
        if data["TotalRecordCount"] > 0:
            return data["Items"][0]["Id"], True
    except: pass

    r = session.post(f"{JELLYFIN_URL}/Playlists", params={"Name": name, "UserId": USER_ID})
    try:
        return r.json()["Id"], False
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nServer response:\n\n", json.dumps(r.json(), indent=4))
        sys.exit(1)

def get_playlist_items(pid):
    try:
        r = session.get(f"{JELLYFIN_URL}/Playlists/{pid}/Items", params={"UserId": USER_ID})
        return {i["Id"] for i in r.json()["Items"]}
    except: return set()

def process_m3us(index_map):
    if not os.path.isdir(M3U_FOLDER):
        print("❌ Folder not found")
        return

    files = [f for f in os.listdir(M3U_FOLDER) if f.endswith(('.m3u', '.m3u8'))]
    files.sort()

    print(f"\n🚀 Processing {len(files)} playlists...")

    for file in files:
        playlist_name = os.path.splitext(file)[0]
        pid, exists = get_or_create_playlist(playlist_name)
        existing_ids = get_playlist_items(pid) if exists else set()

        try:
            with open(os.path.join(M3U_FOLDER, file), 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except: continue

        to_add = []
        missing = []

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"): continue

            fname = os.path.basename(line)
            found_id, reason = find_in_index(fname, index_map)

            if found_id:
                if found_id not in existing_ids and found_id not in to_add:
                    to_add.append(found_id)
            else:
                missing.append(f"{fname} [{reason}]")

        if to_add:
            session.post(f"{JELLYFIN_URL}/Playlists/{pid}/Items",
                         params={"Ids": ",".join(to_add), "UserId": USER_ID})

        if missing:
            print(f"\n📂 Playlist: {playlist_name}")
            for m in missing:
                print(f"❌ MISSING: {m}")

if __name__ == "__main__":
    idx = fetch_library_index()
    process_m3us(idx)
    print("\n🏁 Done.")
