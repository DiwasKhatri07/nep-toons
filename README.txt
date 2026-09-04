# NepToons — Netflix-style cartoon streaming

NepToons is a small Flask streaming library with a cinematic, Netflix-inspired browser UI. The backend keeps movie metadata and stream URLs in `movies.json`, while the frontend is embedded in `test.py` so the project can run with a single Python file.

## Setup

```bash
python3 -m pip install flask pycryptodome
```

Add a current API curl command with its bearer token to `curl.txt` before adding new titles.

## Run

```bash
python3 test.py serve
```

Open **http://localhost:5000** in a browser. The M3U playlist is available at `http://localhost:5000/movies.m3u8` for VLC or compatible players.

## UI features

- Dark cinematic hero section with a red NepToons brand system.
- Responsive horizontal content rails grouped by library category.
- Live title search across movie names, groups, and tags.
- HLS playback page with poster, metadata, and stream proxy support.
- Continue-ready library management panel for adding, previewing, and removing titles.
- Show/season preview with up to four episodes added per action.
- Existing token update, movie add, episode add, delete, JSON database, and stream proxy logic preserved.

## Add or remove titles

From the home page, choose **Manage titles**. The dialog supports:

1. Updating the saved token by pasting a new curl command.
2. Previewing a movie ID, episode curl, show URL, or all-episodes payload.
3. Adding a movie directly or selecting up to four episodes.
4. Removing an existing library title without touching unrelated records.

The JSON database remains `movies.json`; the UI calls the existing `/api/movies`, `/api/curl`, `/api/preview`, `/api/add`, and `/api/delete` endpoints.
