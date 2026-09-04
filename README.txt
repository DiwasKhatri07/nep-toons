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

For production, set a unique secret before starting the server:

```bash
export NEPTOONS_SECRET="replace-with-a-long-random-secret"
```

## UI features

- Dark cinematic hero section with a red NepToons brand system.
- Responsive horizontal content rails grouped by library category.
- Live title search across movie names, groups, and tags.
- HLS playback page with poster, metadata, and stream proxy support.
- Continue Watching rail based on saved playback position.
- My List favorites scoped to the active profile.
- Library management panel for adding, previewing, and removing titles.
- Show/season preview with up to four episodes added per action.

## Accounts and profiles

NepToons now includes local account authentication and profile support:

- Sign up with a name, email, and password.
- Log in and log out using secure HTTP-only cookies.
- Create and switch between multiple viewing profiles.
- Keep My List favorites and watch progress separate for each profile.
- Resume HLS playback from the last saved position.
- A user always keeps at least one profile.

User records are stored in `users.json`, separate from the movie database. Passwords are stored as Werkzeug password hashes, never as plain text. For a shared or public deployment, use HTTPS, set `NEPTOONS_SECRET`, and place the app behind a production WSGI server.

## Add or remove titles

From the home page, choose **Manage titles**. The dialog supports:

1. Updating the saved token by pasting a new curl command.
2. Previewing a movie ID, episode curl, show URL, or all-episodes payload.
3. Adding a movie directly or selecting up to four episodes.
4. Removing an existing library title without touching unrelated records.

The JSON movie database remains `movies.json`; the UI calls the existing `/api/movies`, `/api/curl`, `/api/preview`, `/api/add`, and `/api/delete` endpoints. Authentication and personalization use `/api/auth/*`, `/api/profile`, `/api/profile/favorite`, and `/api/profile/progress`.
