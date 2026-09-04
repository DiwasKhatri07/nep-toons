# NepToons

> **A cinematic cartoon streaming library for Nepali audiences — built with a Netflix-inspired browsing experience, profile personalization, and a lightweight Flask backend.**

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.x-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![HLS](https://img.shields.io/badge/Video-HLS%20Streaming-E50914)](https://developer.apple.com/streaming/)
[![License](https://img.shields.io/badge/License-Private%20Project-6f42c1)](#license)

**NepToons** is a self-hostable cartoon and animation streaming application. It combines a cinematic dark UI with a local movie library, HLS playback, token-based catalog importing, user accounts, multiple profiles, favorites, playback progress, and a JSON-first storage model that is easy to understand and extend.

## Live previews

- **Sandbox full-stack test tunnel:** [Open NepToons](https://8ff92a351b99bf.lhr.life) — temporary; available only while the sandbox process is running.
- **GitHub Pages static preview:** [Open the Pages preview](https://diwaskhatri07.github.io/nep-toons/) — requires GitHub Pages to be enabled for the repository's Actions deployment workflow.
- **Repository:** [github.com/DiwasKhatri07/nep-toons](https://github.com/DiwasKhatri07/nep-toons)

The sandbox link runs the real Flask application. The GitHub Pages version is a frontend-only preview and cannot run Python, authentication, database writes, token updates, or HLS proxy routes.

## Product highlights

### Netflix-inspired discovery

NepToons opens with a cinematic hero banner, grouped horizontal rails, responsive movie cards, live search, ratings, metadata, and a focused watch page. The watch page includes a blurred backdrop, HLS player stage, poster fallback, metadata, description, related titles, My List controls, share action, cinema mode, and keyboard-friendly browser video controls.

### Personal viewing profiles

Users can create an account, log in, log out, and maintain multiple viewing profiles. Every profile has its own favorites and watch progress. Playback progress is saved while a signed-in user watches and can be resumed later from the Continue Watching rail.

### Library management

The existing catalog workflow remains available. Authorized users can update the source curl/token, preview movie IDs or show episodes, add movies or up to four episodes per action, and remove titles from the library without changing the stream proxy implementation.

## How it works

```text
Browser
  │
  ├── Embedded Netflix-style HTML/CSS/JavaScript UI
  │       ├── Search, rails, watch page, profiles, favorites
  │       └── HLS.js / native HLS video playback
  │
  └── Flask application (test.py)
          ├── JSON API for movies, auth, profiles, and progress
          ├── movies.json catalog storage
          ├── users.json account/profile storage
          ├── curl.txt token source
          ├── HLS stream proxy and segment proxy
          └── M3U playlist export for VLC
```

The UI is embedded in `test.py` so the project can run with one Python entry point. The static GitHub Pages preview is maintained separately in `docs/` and uses a copied catalog for browsing-only demonstrations.

## Full-stack technology stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | HTML5, modern CSS, vanilla JavaScript | Responsive streaming interface and interactions |
| UI style | Custom CSS, Google Fonts, dark cinema palette | Netflix-inspired visual hierarchy and motion |
| Video | HTML5 `<video>`, HLS.js, native HLS fallback | Browser playback of HLS playlists |
| Backend | Python 3.11+, Flask | Web server, JSON APIs, streaming proxy |
| Authentication | Werkzeug password hashing, HTTP-only cookies | Local account login and session identity |
| Storage | JSON files | Movie metadata, account records, profiles, favorites, progress |
| Importing | `curl.txt`, Kartoons API integration | Source token and movie/episode metadata lookup |
| Playlist | M3U8 generation | VLC and compatible player support |
| Static hosting | GitHub Pages + GitHub Actions | Frontend-only preview deployment |
| Development | Git, GitHub CLI, Flask test client | Versioning, testing, and repository operations |

## Requirements

- Python **3.11 or newer**
- `pip`
- Internet access for metadata imports, poster images, and stream sources
- A current browser with HLS support or HLS.js support
- Optional: VLC for testing the generated M3U8 playlist

## Local setup

Clone the repository and enter the project directory:

```bash
git clone https://github.com/DiwasKhatri07/nep-toons.git
cd nep-toons
```

Install dependencies:

```bash
python3 -m pip install flask pycryptodome werkzeug
```

Set a unique secret for anything beyond local testing:

```bash
export NEPTOONS_SECRET="replace-this-with-a-long-random-secret"
```

Start the application:

```bash
python3 test.py serve --port 5000
```

Open [http://localhost:5000](http://localhost:5000).

For VLC:

```bash
vlc http://localhost:5000/movies.m3u8
```

## Source token and catalog setup

The catalog importer reads a bearer token from `curl.txt`. Paste a current curl command into that file, then use **Manage titles** from the NepToons UI.

Supported flows include:

1. Paste a fresh curl command to update the source token.
2. Paste a movie ID, episode URL, curl command, or show season payload.
3. Preview the available metadata or episode list.
4. Add one movie or select up to four episodes.
5. Browse, watch, favorite, or remove titles.

The current catalog is stored in `movies.json`. Do not commit private production tokens or sensitive credentials to a public repository.

## API reference

| Method | Route | Description |
|---|---|---|
| `GET` | `/api/movies` | Return the catalog |
| `GET` | `/api/status` | Check whether a source token is available |
| `POST` | `/api/curl` | Update the saved curl/token source |
| `POST` | `/api/preview` | Preview movie, episode, or show input |
| `POST` | `/api/add` | Add movies or selected episodes |
| `POST` | `/api/delete` | Remove a catalog title |
| `GET` | `/api/auth/me` | Return the current signed-in user |
| `POST` | `/api/auth/register` | Create a local account |
| `POST` | `/api/auth/login` | Start an authenticated session |
| `POST` | `/api/auth/logout` | End the current session |
| `POST` | `/api/profile` | Create, switch, or delete profiles |
| `POST` | `/api/profile/favorite` | Toggle a profile favorite |
| `GET/POST` | `/api/profile/progress` | Read or save playback progress |
| `GET` | `/movies.m3u8` | Export the current catalog as M3U8 |
| `GET` | `/stream/<movie>/playlist.m3u8` | Proxy a title stream playlist |
| `GET` | `/seg/<movie>` | Proxy a stream segment |

## Repository structure

```text
nep-toons/
├── test.py                    # Flask app, API, embedded UI, stream proxy
├── movies.json                # Movie and episode catalog
├── users.json                 # Local accounts (created at runtime)
├── curl.txt                  # Source curl/token input
├── docs/
│   ├── index.html             # GitHub Pages static preview
│   ├── movies.json            # Preview catalog copy
│   └── README.md              # Static preview notes
├── .github/workflows/
│   └── pages.yml              # GitHub Pages deployment workflow
└── README.md                  # Project documentation
```

## GitHub Pages preview

The `docs/` directory is intentionally static. It demonstrates the visual system with browsing, search, demo profiles, and browser-local My List favorites. It does not have access to the Flask APIs.

To enable the public Pages preview in GitHub:

1. Open **Settings → Pages** in the repository.
2. Choose **GitHub Actions** as the build and deployment source.
3. Push to `main` or manually run **Deploy NepToons static preview to GitHub Pages**.

Expected URL:

```text
https://diwaskhatri07.github.io/nep-toons/
```

## Security and production notes

This project is designed for learning, testing, and controlled self-hosting. Before production use, move user data and catalog state from JSON files to a database, store secrets in environment variables or a secret manager, serve through HTTPS, run behind a production WSGI server, add rate limiting and CSRF protection, validate stream sources, and configure backups. The Flask development server and temporary tunnels are not production hosting.

## Developer

**Diwas Khatri** is the creator and developer of NepToons. The project name and streaming experience are branded as **Kartoons / NepToons** in the original application implementation.

- Developer: **Diwas Khatri**
- Repository: [DiwasKhatri07/nep-toons](https://github.com/DiwasKhatri07/nep-toons)
- Project: **NepToons — Netflix-style cartoon streaming**

## Contributing

Open an issue with a reproducible description, browser/device details, route information, and screenshots where appropriate. Pull requests should preserve the existing movie add/remove logic, avoid committing tokens, include a clear commit message, and run syntax and route checks before submission.

## License

This repository currently does not declare an open-source license. All rights remain with the project owner, **Diwas Khatri**, unless a license is added by the owner.

## Tags

`neptoons` `kartoons` `cartoon-streaming` `anime-streaming` `nepali-tech` `flask` `python` `hls` `m3u8` `netflix-ui` `profiles` `authentication` `watch-progress` `github-pages` `full-stack` `media-library`
