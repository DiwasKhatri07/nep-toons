# 🎬 KARTOONS — Netflix-style Streaming

Movie/shows add karo aur Netflix-style UI me stream karo.
**Flask sirf backend hai** (M3U/stream/API). UI `web/` folder me (index.html + app.js + style.css).

## Setup (ek baar)
```bash
pip install flask pycryptodome
```

## Files
- `kartoons.py` — Flask backend (M3U + stream proxy + JSON API)
- `web/` — frontend (index.html, app.js, style.css)
- `curl.txt` — apna naya curl yahan daalo (token ke saath)
- `movies.json` — DB (auto)

## Run
```bash
python3 kartoons.py serve
```
Browser: **http://localhost:5000**
VLC: `vlc http://localhost:5000/movies.m3u8`

## Browser se add (1 click)
Home par **+ Add** kholo:
1. **Curl/Token** — naya curl paste karke Update dabao (token save)
2. **Preview** — movie ID, curl, ya poora show ka all-episodes curl/JSON paste karo → Preview
3. **Show** mila to episodes dikhte hain → **select up to 4** → Add Selected (max 4 per click)
4. Movie(s) mili to direct Add

## Features
- Hero banner auto-rotate (har 6s)
- Genre rows + Continue Watching feel
- Search (live)
- Netflix-style player: play/pause, ⏪10/10⏩, seek bar, volume, fullscreen, keyboard
- Movie + Episode dono support
- Delete from Library
