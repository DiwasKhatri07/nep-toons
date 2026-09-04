# NepToons — Nepali Toons Streaming

> **NepToons is a Nepali Toons streaming service created by Diwas Khatri — a beautiful home for cartoons, animated stories, and family-friendly entertainment.**

[![NepToons](https://img.shields.io/badge/NepToons-Nepali%20Toons-E50914?style=for-the-badge)](https://github.com/DiwasKhatri07/nep-toons)
[![Repository](https://img.shields.io/badge/Repository-Public-2ea44f?style=for-the-badge&logo=github)](https://github.com/DiwasKhatri07/nep-toons)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-Backend-000000?style=flat-square&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![HLS](https://img.shields.io/badge/Video-HLS%20%2F%20M3U8-E50914?style=flat-square)](https://developer.apple.com/streaming/)
[![GitHub Pages](https://img.shields.io/badge/Preview-GitHub%20Pages-222222?style=flat-square&logo=github)](https://pages.github.com/)

## NepToons ke ho?

**NepToons** is the main product identity: a Nepali Toons streaming service made and developed by **Diwas Khatri**. The original internal application branding is **Kartoons**, while NepToons is the public-facing name for the Nepali cartoon and animation experience.

Yo Netflix clone hoina. Streaming apps bata familiar usability idea liye pani main purpose Nepali Toons ko own identity, cartoon library, animated stories, and family entertainment ho.

Yo project ko main goal simple cha: **Nepali users ko lagi cartoons ra animated content lai clean, modern, fast, beautiful, and easy-to-use service banaune.**

> **Developer credit:** NepToons is created and developed by **Diwas Khatri**.

## Live links

| Preview | Link | Kasto version ho? |
|---|---|---|
| Public GitHub repository | [github.com/DiwasKhatri07/nep-toons](https://github.com/DiwasKhatri07/nep-toons) | Full public source code |
| Sandbox full-stack preview | [Open NepToons](https://8095d1c807ece8.lhr.life) | Real Flask app; temporary tunnel |
| GitHub Pages static preview | [Open static preview](https://diwaskhatri07.github.io/nep-toons/) | Frontend-only demo; Pages activation may be required |

**Important:** Sandbox tunnel temporary ho. Sandbox sleep or process stop bhayo bhane link off huncha. GitHub Pages le static UI matra serve garcha; Python Flask backend, login, database writes, token update, and HLS proxy GitHub Pages ma run hudaina.

## Demo showcase

Yo 44-second screen recording ma NepToons ko real watch experience, Nepali Toons catalog, player, movie metadata, and dark animated interface dekhaeko cha. Video **Diwas Khatri** ko NepToons demo showcase ho.

**[Watch the NepToons demo recording](https://github.com/DiwasKhatri07/nep-toons/raw/main/docs/demo/neptoons-demo.mp4)**

Demo file: `docs/demo/neptoons-demo.mp4` · H.264/AAC · 1918×1078 · approximately 44 seconds.

## Main features

### NepToons animated streaming interface

- Cinematic hero banner with featured movie.
- Dark red NepToons branding.
- Horizontal category rails.
- Responsive movie and episode cards.
- Search by title, genre, group, and tags.
- Rating, year, duration, episode, and description metadata.
- Smooth hover states and responsive mobile layout.
- Animated visual hierarchy with backdrop gradients, cards, cinema mode, and focused watch layout.

### Professional watch page

- Large HLS video player stage.
- Blurred movie backdrop behind the player.
- Poster fallback while video loads.
- Movie title, group, year, rating, episode, duration, and description.
- **Add to My List** action.
- **Cinema mode** action.
- **Share** action using the current watch URL.
- **More like this** related-title rail.
- Continue watching from saved playback position.
- Native browser HLS support with HLS.js fallback.

### Login and profiles

- Local user registration.
- Login and logout.
- Password hashing with Werkzeug.
- HTTP-only identity cookies.
- Multiple profiles per account.
- Profile switching.
- Separate My List favorites for every profile.
- Separate watch progress for every profile.
- Guest browsing remains possible before login.

### Library management

- Update source curl and bearer token.
- Preview movie IDs and episode links.
- Preview all-episode show payloads.
- Add movies.
- Add selected episodes, maximum four per action.
- Remove titles from the library.
- Preserve existing `movies.json` database and streaming logic.

### Streaming tools

- HLS playlist proxy.
- HLS segment proxy.
- M3U8 playlist export.
- VLC-compatible catalog playlist.
- Browser `<video>` playback.
- HLS.js fallback for browsers without native HLS.

## How NepToons works

```text
User browser
    │
    ├── NepToons streaming-style HTML/CSS/JavaScript UI
    │      ├── Home, search, rails, cards
    │      ├── Login, profiles, My List
    │      ├── Watch page, cinema mode, share
    │      └── HLS.js or native HLS player
    │
    └── Flask application: test.py
           ├── JSON API routes
           ├── Authentication and profile routes
           ├── Movie and episode catalog routes
           ├── HLS stream and segment proxy
           ├── M3U8 playlist generator
           └── Embedded frontend page

Local files
    ├── movies.json  → movie metadata, images, stream URLs
    ├── users.json   → runtime-created users and profiles
    └── curl.txt     → source curl and bearer token input
```

Frontend ra backend ko communication `fetch()` and form requests bata huncha. Movie catalog `movies.json` bata load huncha. User-specific favorites and progress `users.json` ma profile scope bhitra save huncha. Actual video playback `/stream/<movie>/playlist.m3u8` route bata proxy huncha.

## Full tech stack

| Layer | Technology | NepToons ma use |
|---|---|---|
| Language | Python 3.11+ | Backend and catalog logic |
| Backend | Flask | Web server and API routes |
| Frontend | HTML5, CSS3, vanilla JavaScript | Complete streaming UI |
| Typography | Google Fonts: DM Sans and Plus Jakarta Sans | Modern readable interface |
| Video | HTML5 Video, HLS.js | HLS/M3U8 playback |
| Authentication | Werkzeug password hashing, cookies | Local login and identity |
| Storage | JSON files | Catalog and user/profile data |
| Media protocol | HLS and M3U8 | Browser and VLC streaming |
| Crypto | PyCryptodome AES | Source link/token decoding |
| Static preview | GitHub Pages | Frontend-only public demo |
| Automation | GitHub Actions | Pages deployment workflow |
| Version control | Git and GitHub | Public collaboration and releases |

## Requirements

### Required

- Python **3.11 or newer**.
- `pip` package manager.
- Internet connection for metadata, images, and HLS source URLs.
- Modern Chrome, Edge, Firefox, or Safari browser.

### Optional

- VLC for M3U8 playlist testing.
- GitHub CLI (`gh`) for repository management.
- A production WSGI server such as Gunicorn for real deployment.
- A persistent database for production instead of JSON files.

## Full setup — Linux, macOS, or WSL

### Step 1: Clone the public repository

```bash
git clone https://github.com/DiwasKhatri07/nep-toons.git
cd nep-toons
```

### Step 2: Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Step 3: Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install flask pycryptodome werkzeug
```

### Step 4: Configure the application secret

Local testing ma default secret le kaam garcha. Better security ko lagi unique secret set garnu:

Linux/macOS/WSL:

```bash
export NEPTOONS_SECRET="replace-with-a-long-random-secret"
```

Windows PowerShell:

```powershell
$env:NEPTOONS_SECRET="replace-with-a-long-random-secret"
```

### Step 5: Start NepToons

```bash
python3 test.py serve --port 5000
```

Terminal ma yesto URL dekhincha:

```text
http://localhost:5000
```

Browser ma open garnu:

```text
http://localhost:5000
```

### Step 6: Check the API

```bash
curl http://localhost:5000/api/movies
curl http://localhost:5000/api/auth/me
curl http://localhost:5000/movies.m3u8
```

### Step 7: Test VLC

```bash
vlc http://localhost:5000/movies.m3u8
```

## Catalog and token setup — step by step

NepToons ko source catalog import garna `curl.txt` file use huncha.

1. Source service bata current curl command copy garnu.
2. `curl.txt` ma paste garnu.
3. NepToons home page open garnu.
4. **Manage titles** click garnu.
5. **Update token** field ma curl paste garnu.
6. **Update token** click garnu.
7. Movie ID, episode URL, curl, or show-season input paste garnu.
8. **Preview title** click garnu.
9. Movie bhaye **Add to library** click garnu.
10. Show bhaye maximum four episodes select garnu.
11. **Add selected** click garnu.
12. Home rail ma title open garera watch garnu.

**Security warning:** `curl.txt` ma bearer token huncha. Token lai public GitHub commit nagarnu. Production use ma token environment secret or secret manager ma rakhnu.

## User account workflow

1. Home page ma profile button click garnu.
2. **Sign up** select garnu.
3. Name, email, and minimum six-character password enter garnu.
4. Login bhayepachi profile center open garnu.
5. **Add profile** bata family, kids, or personal profile create garnu.
6. Movie card ko heart button bata My List ma save garnu.
7. Video herda signed-in profile ko progress save huncha.
8. Pachi home page ma Continue Watching rail bata resume garnu.

`users.json` runtime ma create huncha ra `.gitignore` ma protected cha. Public repository ma user accounts commit hudaina.

## Important API routes

| Method | Route | Kaam |
|---|---|---|
| `GET` | `/api/movies` | Current movie/episode catalog |
| `GET` | `/api/status` | Source token available cha ki chaina |
| `POST` | `/api/curl` | Curl/token update |
| `POST` | `/api/preview` | Movie, episode, or show preview |
| `POST` | `/api/add` | Movie or selected episode add |
| `POST` | `/api/delete` | Library bata title remove |
| `GET` | `/api/auth/me` | Current login status |
| `POST` | `/api/auth/register` | New account create |
| `POST` | `/api/auth/login` | Account login |
| `POST` | `/api/auth/logout` | Account logout |
| `POST` | `/api/profile` | Create, switch, or delete profile |
| `POST` | `/api/profile/favorite` | Profile My List toggle |
| `GET/POST` | `/api/profile/progress` | Watch progress read/save |
| `GET` | `/movies.m3u8` | VLC-compatible playlist |
| `GET` | `/stream/<movie>/playlist.m3u8` | HLS playlist proxy |
| `GET` | `/seg/<movie>` | HLS segment proxy |

## Project structure

```text
nep-toons/
├── test.py                    # Main Flask app and embedded NepToons UI
├── movies.json                # Movie and episode catalog
├── curl.txt                  # Source curl/token input
├── users.json                 # Runtime user data; ignored by Git
├── docs/
│   ├── index.html             # GitHub Pages frontend-only preview
│   ├── movies.json            # Static preview catalog
│   └── README.md              # Static preview notes
├── .github/workflows/
│   └── pages.yml              # GitHub Pages Actions workflow
├── .gitignore                 # Runtime and secret-file protection
└── README.md                 # This complete guide
```

## GitHub Pages setup

`docs/` ma frontend-only preview cha. GitHub Pages ma Python Flask run hudaina. Static preview ma browsing, search, demo profiles, and browser-local favorites available huncha.

### GitHub ma Pages enable garne

1. Repository open garnu: [DiwasKhatri07/nep-toons](https://github.com/DiwasKhatri07/nep-toons).
2. **Settings** open garnu.
3. Left side ma **Pages** open garnu.
4. **Build and deployment** section ma source **GitHub Actions** select garnu.
5. Save garnu.
6. **Actions** tab ma `Deploy NepToons static preview to GitHub Pages` workflow run garnu.
7. Deployment complete bhayepachi URL open garnu:

```text
https://diwaskhatri07.github.io/nep-toons/
```

## Temporary public tunnel setup

Local app lai quick testing ko lagi localhost.run use garna sakincha:

```bash
python3 test.py serve --port 5000
ssh -R 80:localhost:5000 nokey@localhost.run
```

Command le temporary `https://....lhr.life` URL dincha. Yo URL sandbox, terminal, or tunnel stop bhaye pachi off huncha. Production hosting ko replacement hoina.

## Developer credits

### Created by Diwas Khatri

**Diwas Khatri** is the developer and project owner behind NepToons. The original implementation branding is **Kartoons**, while the public product identity is **NepToons — Nepali Toons Streaming**, created by **Diwas Khatri**.

- Developer: **Diwas Khatri**
- Project: **NepToons / Kartoons**
- Repository: [DiwasKhatri07/nep-toons](https://github.com/DiwasKhatri07/nep-toons)
- Product focus: Nepali cartoon and animation streaming
- Interface direction: streaming-style cinema UI

## Production checklist

Before public production deployment, the following improvements are recommended:

- Replace JSON storage with PostgreSQL, MySQL, or SQLite.
- Use a production WSGI server such as Gunicorn.
- Put the service behind HTTPS and a reverse proxy.
- Set a long random `NEPTOONS_SECRET`.
- Move curl tokens and stream secrets into environment variables.
- Add CSRF protection, rate limits, and account lockout rules.
- Add email verification and password reset.
- Validate every external stream URL.
- Add database backups and migration scripts.
- Add monitoring, logs, and error reporting.
- Respect copyright, provider terms, and regional streaming rules.

## Contribution guide

Contribution garna:

1. Repository fork garnu.
2. Feature branch create garnu.
3. UI or backend change carefully test garnu.
4. Existing add/remove and streaming logic break nagarnu.
5. Token, password, `users.json`, or private credentials commit nagarnu.
6. README ma new feature documentation add garnu.
7. Clear pull request description create garnu.

## License

This repository currently has no open-source license. Copyright and project ownership remain with **Diwas Khatri** unless the repository owner adds a license.

## Tags

`neptoons` `nepali-toons` `nepali-cartoon` `nepali-animation` `kartoons` `cartoon-streaming` `anime-streaming` `family-streaming` `kids-streaming` `flask` `python` `hls` `m3u8` `video-streaming` `netflix-ui` `cinema-ui` `dark-ui` `responsive-ui` `animated-ui` `watch-page` `profiles` `authentication` `user-profiles` `favorites` `my-list` `continue-watching` `watch-progress` `movie-library` `media-library` `github-pages` `github-actions` `full-stack` `self-hosted` `open-source-project` `nepali-tech` `diwas-khatri`

## References

[1]: https://flask.palletsprojects.com/ "Flask Documentation"
[2]: https://developer.apple.com/streaming/ "HTTP Live Streaming Overview"
[3]: https://docs.github.com/en/pages "GitHub Pages Documentation"
[4]: https://docs.github.com/en/actions "GitHub Actions Documentation"
[5]: https://www.python.org/doc/ "Python Documentation"
