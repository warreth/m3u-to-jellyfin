# Jellyfin Smart M3U Importer

This script imports local `.m3u` or `.m3u8` playlists into Jellyfin as **native, editable playlists**.

I created this because Jellyfin treats local m3u files as "Read-Only." I wanted to be able to edit my playlists within the Jellyfin UI. Additionally, if you use tools like Beets or MusicBrainz to organize your library, your filenames often change, breaking old m3u playlists. This script uses "Fuzzy Matching" to find the correct songs even if the filenames don't match exactly.

## Features

*   **Smart Indexing:** Fetches your library once at the start (fast) and builds a lookup index in memory.
*   **Fuzzy Matching:** Can match "The Black Eyed Peas - I Gotta Feeling" to "Black Eyed Peas - I Gotta Feeling" or handle small typos.
*   **Deep Cleaning:** Ignores "junk" data in filenames like:
    *   `[Official Video]`, `(Lyrics)`, `[4K]`
    *   `ft.`, `feat.`, `with`
    *   Leading "The"
*   **Update Mode:** Checks if the playlist already exists. It only adds missing tracks and skips duplicates.
*   **Non-Destructive:** Uses the Jellyfin API. It does not touch your database files directly.

## Requirements

*   Python 3
*   `requests` library

```bash
pip install requests
```

## Configuration

Open the script and edit the top section:

*   `JELLYFIN_URL`: Your server URL (e.g., `http://localhost:8096`)
*   `API_KEY`: Generate this in **Dashboard -> API Keys**.
*   `USER_ID`: Found in the URL when you click on your user profile in the dashboard.
*   `M3U_FOLDER`: The local path to the folder containing your `.m3u` files.

## Usage

Run the script:

```bash
python3 smart_import.py
```

The script runs in "Quiet Mode." It will process the playlists and only output filenames that it absolutely cannot find in your library.


Hopefully this helps someone else with a messy library.
I recommend to delete the m3u8 files afterwards, otherwise you will have duplicated playlists.

## License
see the License file (AGPLv3)
