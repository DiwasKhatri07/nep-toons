#!/usr/bin/env python3
"""
Kartoons — Netflix-style streaming (Flask BACKEND only)
========================================================
Flask sirf backend hai: M3U / stream / segment proxy / JSON API.
UI alag files me: index.html + app.js (Netflix-style SPA).

Setup:
    pip install flask pycryptodome
    curl.txt me apna naya curl daalo (token ke saath)

RUN:
    python3 kartoons.py serve      # http://localhost:5000

CLI add (optional):
    python3 kartoons.py add <id>
"""

import sys
import os
import json
import time
import base64
import hashlib
import re
import threading
import urllib.request
import urllib.parse

try:
    from flask import Flask, Response, request, send_from_directory
except ImportError:
    sys.exit("pip install flask")

from Crypto.Cipher import AES

API = "https://api.kartoons.me/api"
DB_FILE = "movies.json"
CURL_FILE = "curl.txt"

# static keys (kabhi nahi badalte)
KEY_CBC = b"bca9e0df1a5abb32906ca3f63ac04cef".ljust(32, b" ")
KEY_GCM = hashlib.sha256(
    ("pmS0CAMG1Ruq49WbMyhE3fh1sOuLYEL9"
     + "rtFazYYljVI2j4BPSog73hW7A7xMhceHD0iwrPrVVDXLvxyWr").encode()
).digest()

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36")

app = Flask(__name__)


# --------------------------- crypto -------------------------------
def b64url(s):
    b = s.replace("-", "+").replace("_", "/")
    b += "=" * (-len(b) % 4)
    return base64.b64decode(b)


def unpad(p):
    pad = p[-1]
    return p[:-pad] if 1 <= pad <= 16 and p[-pad:] == bytes([pad]) * pad else p


def dec_cbc(blob):
    r = b64url(blob)
    return unpad(AES.new(KEY_CBC, AES.MODE_CBC, r[:16]).decrypt(r[16:])).decode()


def dec_gcm(tok):
    r = b64url(tok)
    return AES.new(KEY_GCM, AES.MODE_GCM, nonce=r[:12]).decrypt_and_verify(r[12:-16], r[-16:]).decode()


def leading_bits(b):
    bits = 0
    for byte in b:
        if byte == 0:
            bits += 8
            continue
        m = 0x80
        while m and not (byte & m):
            bits += 1
            m >>= 1
        break
    return bits


def solve_pow(nonce, bits, limit=20_000_000):
    for c in range(limit):
        if leading_bits(hashlib.sha256(f"{nonce}:{c}".encode()).digest()) >= bits:
            return str(c)
    raise RuntimeError("pow unsolved")


# --------------------------- http -------------------------------
def http_json(url, headers):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}


def http_bytes(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, r.read(), r.headers.get("Content-Type", "")


# --------------------------- token -------------------------------
def get_token():
    try:
        content = open(CURL_FILE, encoding="utf-8").read()
    except FileNotFoundError:
        return None
    m = re.search(r"Bearer\s+([A-Za-z0-9_.\-]+)", content)
    return m.group(1) if m else None


def id_from_curl(text):
    m = re.search(r"/(?:movies|shows/episode)/([0-9a-f]+)", text)
    return (m.group(1), "episode" if "episode" in m.group(0) else "movie") if m else None


def token_from_text(text):
    m = re.search(r"Bearer\s+([A-Za-z0-9_.\-]+)", text)
    return m.group(1) if m else None


def pow_headers(movie, kind="movie"):
    content = f"{kind}:{movie}" if kind in ("movie", "episode") else f"movie:{movie}"
    _, ch = http_json(API + "/challenge/pow?content=" + urllib.parse.quote(content),
                      {"User-Agent": UA, "Accept": "application/json"})
    d = ch.get("data", {})
    if not d.get("nonce"):
        return {}
    return {"X-Pow-Nonce": d["nonce"], "X-Pow-Solution": solve_pow(d["nonce"], d["bits"])}


# --------------------------- data -------------------------------
def fetch_meta(movie, token, kind="movie"):
    h = {"User-Agent": UA, "Accept": "application/json", "Origin": "https://kartoons.me",
         "Referer": "https://kartoons.me/", "Authorization": "Bearer " + token}
    if kind == "episode":
        code, js = http_json(f"{API}/shows/episode/{movie}", h)
    else:
        code, js = http_json(f"{API}/movies/{movie}", h)
    if code in (401, 403):
        raise RuntimeError("token_expired")
    if code == 429:
        raise RuntimeError("rate_limited")
    if code == 404 or not (js.get("data") or {}):
        raise RuntimeError("not_found")
    d = js.get("data", {}) or {}
    if kind == "episode":
        show = d.get("seasonId", {}).get("showId", {}) or {}
        season = d.get("seasonId", {}).get("seasonNumber")
        ep = d.get("episodeNumber")
        ep_label = f"S{season}E{ep}" if season and ep else ""
        title = show.get("title") or d.get("title") or movie
        if ep_label:
            title = f"{title} · {ep_label}"
        return {
            "id": movie, "kind": "episode", "title": title,
            "description": d.get("description") or "",
            "image": show.get("image") or d.get("image") or "",
            "year": show.get("releaseYear") or d.get("releaseYear"),
            "rating": d.get("rating") or show.get("rating"),
            "duration": d.get("durationMinutes") or d.get("duration"),
            "tags": d.get("tags") or show.get("tags") or [],
            "group": d.get("category") or show.get("type") or "Series",
            "episode": ep_label,
        }
    return {
        "id": movie, "kind": "movie", "title": d.get("title") or movie,
        "description": d.get("description") or "",
        "image": d.get("image") or d.get("coverImage") or "",
        "year": d.get("releaseYear"), "rating": d.get("rating"),
        "duration": d.get("durationMinutes") or d.get("duration"),
        "tags": d.get("tags") or [], "group": d.get("category") or "Cartoon",
    }


def fetch_stream(movie, token, kind="movie"):
    h = {"User-Agent": UA, "Accept": "application/json, text/plain, */*",
         "Origin": "https://kartoons.me", "Referer": "https://kartoons.me/",
         "Authorization": "Bearer " + token}
    h.update(pow_headers(movie, kind))
    if kind == "episode":
        code, js = http_json(f"{API}/shows/episode/{movie}/links", h)
    else:
        code, js = http_json(f"{API}/movies/{movie}/links", h)
    if code in (401, 403):
        raise RuntimeError("token_expired")
    if code == 429:
        raise RuntimeError("rate_limited")
    if code == 404:
        raise RuntimeError("not_found")
    if code != 200:
        raise RuntimeError(f"links HTTP {code}")
    data = js.get("data", {})
    payload = data.get("links") or (data if isinstance(data, list) else [])
    if isinstance(data, dict) and not payload:
        for v in data.values():
            if isinstance(v, list) and v:
                payload = v
                break
    urls = [l.get("url") for l in payload if l.get("url")]
    if not urls:
        raise RuntimeError("no links")
    master = dec_cbc(urls[0])
    _, body, _ = http_bytes(master, {"User-Agent": UA, "Referer": "https://kartoons.me/"})
    variants = [dec_gcm(l[5:]) for l in body.decode("utf-8", "replace").splitlines()
                if l.startswith("enc2:")]
    return variants[0] if variants else master


def _add_impl(mid, token, kind):
    db = load_db()
    meta = fetch_meta(mid, token, kind)
    meta["stream"] = fetch_stream(mid, token, kind)
    if any(x["id"] == mid for x in db):
        db = [meta if x["id"] == mid else x for x in db]
        save_db(db)
        return True, f"Updated: {meta['title']}"
    db.append(meta)
    save_db(db)
    return True, f"Added: {meta['title']}"


def add_movie(mid, token, kind="auto"):
    order = ["movie", "episode"] if kind == "auto" else [kind]
    last = ""
    for k in order:
        try:
            return _add_impl(mid, token, k)
        except RuntimeError as e:
            if str(e) == "not_found" and k == "movie" and "episode" in order:
                last = "movie me nahi mila, episode try karta hoon..."
                continue
            raise
    raise RuntimeError(last)


# --------------------------- all-episodes support -------------------------------
def parse_all_episodes(text):
    m = re.search(r"/shows/([0-9a-f]+)/season/([0-9a-f]+)/all-episodes", text)
    return (m.group(1), m.group(2)) if m else None


def fetch_episodes_json(show_id, season_id, token):
    h = {"User-Agent": UA, "Accept": "application/json, text/plain, */*",
         "Origin": "https://kartoons.me", "Referer": "https://kartoons.me/",
         "Authorization": "Bearer " + token}
    code, js = http_json(f"{API}/shows/{show_id}/season/{season_id}/all-episodes", h)
    if code in (401, 403):
        raise RuntimeError("token_expired")
    if code == 429:
        raise RuntimeError("rate_limited")
    if code != 200:
        raise RuntimeError(f"episodes HTTP {code}")
    return js


def parse_episodes_from_json(obj):
    if isinstance(obj, str):
        obj = json.loads(obj)
    data = obj.get("data", obj) if isinstance(obj, dict) else obj
    show = obj.get("show", {}) if isinstance(obj, dict) else {}
    season = obj.get("season", {}) if isinstance(obj, dict) else {}
    show_title = show.get("title") or "Show"
    season_num = season.get("seasonNumber")
    eps = []
    if isinstance(data, list):
        for e in data:
            if not isinstance(e, dict):
                continue
            sn = e.get("seasonId")
            sn = sn.get("seasonNumber") if isinstance(sn, dict) else (season_num or 1)
            en = e.get("episodeNumber") or 1
            eps.append({
                "id": e.get("_id"), "episode": f"S{sn}E{en}",
                "title": f"{show_title} · S{sn}E{en}", "show": show_title,
                "episodeTitle": e.get("title") or "",
                "description": e.get("description") or "",
                "image": show.get("image") or "",
            })
    return eps


def add_episode_batch(eps, token, gap=1.5, retries=3):
    ok, err = [], []
    for i, e in enumerate(eps):
        attempt = 0
        while True:
            try:
                meta = fetch_meta(e["id"], token, "episode")
                meta["stream"] = fetch_stream(e["id"], token, "episode")
                db = load_db()
                if any(x["id"] == e["id"] for x in db):
                    db = [meta if x["id"] == e["id"] else x for x in db]
                else:
                    db.append(meta)
                save_db(db)
                ok.append(meta["title"])
                break
            except RuntimeError as ex:
                if str(ex) == "rate_limited" and attempt < retries:
                    attempt += 1
                    time.sleep(8)
                    continue
                err.append(f"{e.get('episode','?')}: " + {"token_expired": "token expired",
                                                       "rate_limited": "rate limited (429)"}.get(str(ex), str(ex)))
                break
            except Exception as ex:
                err.append(f"{e.get('episode','?')}: {ex}")
                break
        if i < len(eps) - 1:
            time.sleep(gap)
    return ok, err


# --------------------------- db -------------------------------
def load_db():
    try:
        return json.load(open(DB_FILE, encoding="utf-8"))
    except Exception:
        return []


def save_db(db):
    json.dump(db, open(DB_FILE, "w", encoding="utf-8"), indent=2)


# --------------------------- CLI add -------------------------------
def extract_ids(args):
    ids = []
    for a in args:
        if a == "--file":
            continue
        if a.startswith("http") or a.startswith("curl") or "movies/" in a or "episode/" in a:
            r = id_from_curl(a)
            if r:
                ids.append(r)
        else:
            ids.append((a.strip(), "auto"))
    return ids


def cmd_add(args):
    token = get_token()
    items = extract_ids(args)
    if not items:
        r = id_from_curl(open(CURL_FILE, encoding="utf-8").read()) if _has_curl() else None
        if r:
            items = [r]
            print(f"[*] curl.txt se: {r[0]} ({r[1]})")
        else:
            print("Koi ID nahi mili. Use: python3 kartoons.py add <id> | add 'curl...' | add")
            return
    if not token:
        print("[!] curl.txt me token nahi. Naya curl daalo.")
        return
    ok = 0
    for mid, kind in items:
        print(f"\n--- {mid} ({kind}) ---")
        try:
            done, msg = add_movie(mid, token, kind)
            print(f"  {'[+]' if done else '[~]'} {msg}")
            ok += 1
        except RuntimeError as e:
            if "token_expired" in str(e):
                print("  [x] TOKEN EXPIRED — curl.txt naya daalo")
                return
            if "rate_limited" in str(e):
                print("  [x] Rate limited (429) — thoda ruk kar dobara try karo")
                return
            print(f"  [x] {e}")
        except Exception as e:
            print(f"  [x] {e}")
    print(f"\nDone. {ok}/{len(items)} added. Total: {len(load_db())} movies")


def _has_curl():
    try:
        open(CURL_FILE, encoding="utf-8").read()
        return True
    except Exception:
        return False


# ====================================================================

# ====================================================================
#                     INLINE FRONTEND (no web/ folder needed)
# ====================================================================
PAGE = '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">\n<title>NepToons — Watch your favorites</title>\n<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@600;700;800&display=swap" rel="stylesheet">\n<script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>\n<style>\n:root{--bg:#09090b;--panel:#151518;--panel2:#1d1d22;--muted:#a6a6ad;--line:#2c2c32;--red:#e50914;--red2:#ff3b45;--white:#f7f7f8;--ease:cubic-bezier(.23,1,.32,1)}\n*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--white);font:14px \'DM Sans\',system-ui,sans-serif}button,input,textarea{font:inherit}button{cursor:pointer;border:0;color:inherit}a{color:inherit;text-decoration:none}.shell{min-height:100vh;background:radial-gradient(circle at 80% 0%,#251016 0,transparent 28rem),var(--bg)}\n.nav{height:72px;display:flex;align-items:center;gap:28px;padding:0 5%;position:fixed;top:0;left:0;right:0;z-index:20;transition:.25s background}.nav.scrolled{background:rgba(9,9,11,.94);backdrop-filter:blur(14px);border-bottom:1px solid #242428}.brand{font:800 20px \'Plus Jakarta Sans\';letter-spacing:-1px;color:var(--red);white-space:nowrap}.brand span{color:#fff}.links{display:flex;gap:20px;color:#c9c9cd}.links a:hover,.links a.active{color:#fff}.nav-actions{margin-left:auto;display:flex;align-items:center;gap:14px}.search{display:flex;align-items:center;background:#1d1d21;border:1px solid #34343a;border-radius:8px;padding:0 10px;transition:.2s}.search:focus-within{border-color:#777}.search input{background:transparent;border:0;outline:0;color:#fff;width:0;padding:9px 0;transition:.25s}.search:focus-within input{width:170px;padding-left:8px}.icon-btn,.round{background:#242429;border-radius:50%;width:36px;height:36px;display:grid;place-items:center}.hero{min-height:650px;padding:180px 5% 80px;display:flex;align-items:flex-end;position:relative;overflow:hidden;background:linear-gradient(90deg,rgba(9,9,11,.98) 0%,rgba(9,9,11,.74) 38%,rgba(9,9,11,.04) 78%),linear-gradient(0deg,var(--bg) 0%,transparent 28%),url(\'https://image.tmdb.org/t/p/original/uux6M8z3hxLDkq8LXSzq8528mrq.jpg\') center/cover no-repeat}.hero:after{content:\'\';position:absolute;inset:0;background:linear-gradient(0deg,var(--bg),transparent 40%);pointer-events:none}.hero-content{position:relative;z-index:1;max-width:590px}.eyebrow{color:#ffb1b5;text-transform:uppercase;letter-spacing:2px;font-size:11px;font-weight:700}.hero h1{font:800 clamp(38px,5vw,72px)/1.02 \'Plus Jakarta Sans\';letter-spacing:-3px;margin:16px 0}.hero p{font-size:16px;line-height:1.6;color:#d1d1d5;max-width:520px}.meta{display:flex;gap:15px;align-items:center;color:#ddd;margin:18px 0}.rating{color:#ffd35c}.cta{display:flex;gap:12px;flex-wrap:wrap;margin-top:26px}.btn{padding:12px 19px;border-radius:7px;font-weight:700;transition:.18s transform,.18s background}.btn:active{transform:scale(.97)}.btn-primary{background:#fff;color:#111}.btn-primary:hover{background:#ddd}.btn-red{background:var(--red)}.btn-red:hover{background:var(--red2)}.btn-ghost{background:#29292e}.content{padding:0 5% 60px}.section{margin:28px 0 42px}.section-head{display:flex;justify-content:space-between;align-items:end;margin-bottom:15px}.section h2{font:700 20px \'Plus Jakarta Sans\';margin:0}.section-kicker{font-size:12px;color:var(--muted)}.rail{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(180px,1fr);gap:14px;overflow-x:auto;padding:4px 2px 13px;scrollbar-width:thin;scrollbar-color:#3d3d42 transparent}.card{min-width:0;position:relative;border-radius:9px;overflow:hidden;background:#17171a;transition:transform .22s var(--ease),box-shadow .22s;isolation:isolate}.card:hover{transform:translateY(-6px) scale(1.025);z-index:2;box-shadow:0 18px 35px #000b}.poster{aspect-ratio:2/3;background:#26262b;overflow:hidden}.poster img{width:100%;height:100%;display:block;object-fit:cover;transition:.3s}.card:hover .poster img{transform:scale(1.06)}.card-info{padding:11px 11px 13px}.card-title{font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.card-sub{font-size:12px;color:#a6a6ad;margin-top:6px}.play-badge{position:absolute;right:10px;top:10px;background:var(--red);width:30px;height:30px;border-radius:50%;display:grid;place-items:center;opacity:0;transform:translateY(4px);transition:.2s}.card:hover .play-badge{opacity:1;transform:none}.empty{border:1px dashed #35353a;border-radius:10px;padding:30px;color:var(--muted);text-align:center}.manage{display:flex;align-items:center;justify-content:space-between;background:linear-gradient(110deg,#1b1013,#17171b);border:1px solid #392228;border-radius:13px;padding:22px 24px}.manage strong{font-size:17px}.manage p{color:var(--muted);margin:5px 0 0}.overlay{position:fixed;inset:0;background:#000b;z-index:50;display:grid;place-items:center;padding:20px}.hidden{display:none!important}.modal{background:#151518;border:1px solid #36363b;border-radius:15px;width:min(720px,100%);max-height:90vh;overflow:auto;padding:25px;box-shadow:0 24px 80px #000}.modal-head{display:flex;justify-content:space-between;align-items:start;margin-bottom:18px}.modal h2{font:700 25px \'Plus Jakarta Sans\';margin:0}.close{background:transparent;font-size:25px;color:#aaa}.field{margin:14px 0}.field label{display:block;color:#cfcfd3;font-size:12px;font-weight:700;margin-bottom:7px}.field textarea{width:100%;min-height:95px;resize:vertical;background:#0d0d0f;border:1px solid #36363b;border-radius:8px;padding:12px;color:#fff;outline:0}.field textarea:focus{border-color:#9c3b43}.status{margin:14px 0;padding:12px;border-radius:8px;background:#222228;color:#ddd}.status.error{color:#ffb0b4;background:#35171b}.lib{display:grid;gap:8px;margin-top:18px}.lib-row{display:flex;align-items:center;gap:12px;padding:8px;background:#202025;border-radius:8px}.lib-row img{width:42px;height:58px;object-fit:cover;border-radius:4px}.lib-row .grow{flex:1;min-width:0}.lib-row b{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.lib-row small{color:var(--muted)}.delete{background:#342125;color:#ff9ca2;border-radius:6px;padding:8px 10px}.episode-list{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0}.episode-list label{background:#28282e;padding:8px 10px;border-radius:6px;color:#ddd}.episode-list label:has(input:checked){background:#8d1821}.player-page{padding:110px 5% 50px;min-height:100vh}.player-wrap{background:#000;border-radius:12px;overflow:hidden;max-width:1100px;margin:auto}.player-wrap video{display:block;width:100%;max-height:70vh}.back{color:#bbb;margin-bottom:18px;display:inline-block}.back:hover{color:#fff}.player-title{max-width:1100px;margin:18px auto}.player-title h1{font:700 28px \'Plus Jakarta Sans\';margin:0 0 8px}.player-title p{color:var(--muted);line-height:1.6}.toast{position:fixed;bottom:25px;right:25px;background:#fff;color:#111;padding:12px 16px;border-radius:8px;z-index:80;box-shadow:0 8px 30px #0008}.loader{color:var(--muted);padding:30px 0}@media(max-width:700px){.nav{padding:0 20px;gap:15px}.links{display:none}.content,.hero{padding-left:20px;padding-right:20px}.hero{min-height:620px}.hero h1{letter-spacing:-2px}.rail{grid-auto-columns:145px}.manage{align-items:flex-start;gap:14px;flex-direction:column}.search:focus-within input{width:110px}}\n</style></head>\n<body><div id="app" class="shell"></div><div id="overlay" class="overlay hidden"></div><div id="toast" class="toast hidden"></div>\n<script>\nconst app=document.getElementById(\'app\'),overlay=document.getElementById(\'overlay\');let db=[],searchTerm=\'\';\nconst esc=s=>String(s??\'\').replace(/[&<>"\']/g,c=>({\'&\':\'&amp;\',\'<\':\'&lt;\',\'>\':\'&gt;\',\'"\':\'&quot;\',"\'":\'&#039;\'}[c]));\nasync function post(url,data){const f=new FormData();Object.entries(data).forEach(([k,v])=>f.append(k,v));const r=await fetch(url,{method:\'POST\',body:f});return r.json()}\nasync function load(){const r=await fetch(\'/api/movies\');db=await r.json();return db}\nfunction toast(t){const el=document.getElementById(\'toast\');el.textContent=t;el.classList.remove(\'hidden\');setTimeout(()=>el.classList.add(\'hidden\'),2800)}\nfunction nav(){return `<nav class="nav" id="nav"><a class="brand" href="/">NEP<span>TOONS</span></a><div class="links"><a class="active" href="#home">Home</a><a href="#library">My Library</a><a href="#browse">Browse</a></div><div class="nav-actions"><label class="search">⌕<input id="search" placeholder="Search titles" oninput="searchTerm=this.value;renderHome()"></label><button class="icon-btn" title="Manage library" onclick="openAdd()">＋</button></div></nav>`}\nfunction card(m){return `<article class="card"><a href="/watch/${encodeURIComponent(m.id)}"><div class="poster"><img src="${esc(m.image)}" loading="lazy" onerror="this.src=\'https://placehold.co/400x600/202024/ffffff?text=NepToons\'"></div><span class="play-badge">▶</span><div class="card-info"><div class="card-title" title="${esc(m.title)}">${esc(m.title)}</div><div class="card-sub">${esc(m.year||\'Series\')} · ${m.rating?\'★ \'+esc(m.rating):esc(m.episode||\'Movie\')}</div></div></a></article>`}\nfunction rail(title,items,kicker=\'\'){if(!items.length)return \'\';return `<section class="section"><div class="section-head"><h2>${title}</h2><span class="section-kicker">${kicker}</span></div><div class="rail">${items.map(card).join(\'\')}</div></section>`}\nfunction renderHome(){const q=searchTerm.toLowerCase().trim();const items=db.filter(m=>!q||(`${m.title} ${m.group} ${(m.tags||[]).join(\' \')}`).toLowerCase().includes(q));const featured=items[0]||db[0];if(!featured){app.innerHTML=nav()+`<main class="content" style="padding-top:120px"><div class="empty">Your library is empty. Add your first movie to start watching.</div></main>`;return}const groups={};items.forEach(m=>(groups[m.group||\'Featured\']??=[]).push(m));app.innerHTML=nav()+`<header class="hero" id="home" style="background-image:linear-gradient(90deg,rgba(9,9,11,.98) 0%,rgba(9,9,11,.72) 38%,rgba(9,9,11,.08) 78%),linear-gradient(0deg,var(--bg),transparent 38%),url(\'${esc(featured.image)}\')"><div class="hero-content"><div class="eyebrow">NepToons original library</div><h1>${esc(featured.title)}</h1><div class="meta"><span>${esc(featured.year||\'Now streaming\')}</span><span class="rating">★ ${esc(featured.rating||\'8.0\')}</span><span>${featured.duration?esc(featured.duration)+\' min\':\'Feature\'}</span></div><p>${esc(featured.description||\'Your next favorite animated adventure is waiting.\')}</p><div class="cta"><a class="btn btn-primary" href="/watch/${encodeURIComponent(featured.id)}">▶ &nbsp;Play now</a><button class="btn btn-ghost" onclick="openAdd()">＋ &nbsp;Manage library</button></div></div></header><main class="content" id="browse"><div class="manage" id="library"><div><strong>Your library</strong><p>${db.length} titles ready to stream · Add or remove titles anytime</p></div><button class="btn btn-red" onclick="openAdd()">Manage titles</button></div>${q?rail(\'Search results\',items,`${items.length} found`):Object.entries(groups).map(([g,arr])=>rail(g,arr,`${arr.length} title${arr.length===1?\'\':\'s\'}`)).join(\'\')}</main>`}\nfunction openAdd(){overlay.classList.remove(\'hidden\');overlay.innerHTML=`<div class="modal"><div class="modal-head"><div><div class="eyebrow">Library control</div><h2>Add or remove titles</h2></div><button class="close" onclick="closeAdd()">×</button></div><div class="field"><label>UPDATE TOKEN / CURL</label><textarea id="curlbox" placeholder="Paste the latest curl command here to refresh your token"></textarea><button class="btn btn-ghost" onclick="updateCurl()">Update token</button></div><div class="field"><label>ADD MOVIE, EPISODE, OR SHOW</label><textarea id="addbox" placeholder="Paste an ID, curl, or all-episodes URL"></textarea><button class="btn btn-red" onclick="preview()">Preview title</button></div><div id="pv"></div><div class="field"><label>YOUR TITLES (${db.length})</label><div class="lib" id="lib">${db.map(m=>`<div class="lib-row"><img src="${esc(m.image)}"><div class="grow"><b>${esc(m.title)}</b><small>${esc(m.year||\'Series\')} · ${esc(m.episode||\'Movie\')}</small></div><button class="delete" onclick="delMovie(\'${esc(m.id)}\')">Remove</button></div>`).join(\'\')||\'<div class="empty">No titles yet.</div>\'}</div></div></div>`}\nfunction closeAdd(){overlay.classList.add(\'hidden\');overlay.innerHTML=\'\'}\nfunction setStatus(t,err=false){document.getElementById(\'pv\').innerHTML=`<div class="status ${err?\'error\':\'\'}">${t}</div>`}\nasync function updateCurl(){const t=document.getElementById(\'curlbox\').value;if(!t)return setStatus(\'Paste a curl command first.\',true);const r=await post(\'/api/curl\',{curl:t});setStatus(r.ok?\'Token updated. You can add titles now.\':r.err,!r.ok);if(r.ok)toast(\'Token updated\')}\nasync function preview(){const t=document.getElementById(\'addbox\').value;if(!t)return setStatus(\'Paste an ID, curl, or show link first.\',true);setStatus(\'Finding titles…\');const r=await post(\'/api/preview\',{input:t});if(!r.ok)return setStatus(r.err||\'Could not find that title.\',true);if(r.type===\'show\'){document.getElementById(\'pv\').innerHTML=`<div class="status"><b>${esc(r.show)}</b> · ${r.episodes.length} episodes found</div><div class="episode-list" id="eps">${r.episodes.map(e=>`<label><input type="checkbox" value="${esc(e.id)}|${esc(e.episode)}"> ${esc(e.episode)}</label>`).join(\'\')}</div><button class="btn btn-red" onclick="addSelected()">Add selected (max 4)</button>`}else document.getElementById(\'pv\').innerHTML=`<div class="status">${r.items.length} title${r.items.length===1?\'\':\'s\'} found</div><button class="btn btn-red" onclick="addRaw()">Add to library</button>`}\nasync function addSelected(){const selected=[...document.querySelectorAll(\'#eps input:checked\')].map(x=>x.value);if(!selected.length)return setStatus(\'Select at least one episode.\',true);if(selected.length>4)return setStatus(\'Select up to 4 episodes at a time.\',true);setStatus(\'Adding selected episodes…\');const r=await post(\'/api/add\',{episodes:selected.join(\',\')});if(r.ok){await load();openAdd();toast(\'Titles added\')}else setStatus(r.err||\'Could not add titles.\',true)}\nasync function addRaw(){setStatus(\'Adding title…\');const r=await post(\'/api/add\',{input:document.getElementById(\'addbox\').value});if(r.ok){await load();openAdd();toast(\'Title added\')}else setStatus(r.err||\'Could not add title.\',true)}\nasync function delMovie(id){if(!confirm(\'Remove this title from your library?\'))return;const r=await post(\'/api/delete\',{id});if(r.ok){await load();openAdd();renderHome();toast(\'Title removed\')}else setStatus(r.err||\'Could not remove title.\',true)}\nasync function watch(id){await load();const m=db.find(x=>x.id===id);if(!m){location.href=\'/\';return}app.innerHTML=nav()+`<main class="player-page"><a class="back" href="/">← Back to library</a><div class="player-wrap"><video id="video" controls playsinline poster="${esc(m.image)}"></video></div><div class="player-title"><div class="eyebrow">Now playing</div><h1>${esc(m.title)}</h1><div class="meta"><span>${esc(m.year||\'Series\')}</span><span class="rating">★ ${esc(m.rating||\'—\')}</span><span>${esc(m.episode||\'Movie\')}</span></div><p>${esc(m.description||\'\')}</p></div></main>`;const v=document.getElementById(\'video\'),src=\'/stream/\'+encodeURIComponent(id)+\'/playlist.m3u8\';if(v.canPlayType(\'application/vnd.apple.mpegurl\'))v.src=src;else if(window.Hls&&Hls.isSupported()){const h=new Hls();h.loadSource(src);h.attachMedia(v)}else v.outerHTML=\'<div class="empty">This browser does not support HLS playback.</div>\'}\nwindow.addEventListener(\'scroll\',()=>document.getElementById(\'nav\')?.classList.toggle(\'scrolled\',scrollY>30));\n(async()=>{await load();const m=location.pathname.match(/^\\/watch\\/([^/]+)/);if(m)watch(decodeURIComponent(m[1]));else renderHome()})();\n</script></body></html>\n'
@app.route("/")
@app.route("/watch/<path:movie>")
@app.route("/<path:anything>")
def serve(**kwargs):
    # SPA — sab kuch inline, koi external file nahi
    return Response(PAGE, mimetype="text/html")


# ====================================================================




@app.route("/api/movies")
def api_movies():
    return Response(json.dumps(load_db()), mimetype="application/json")


@app.route("/api/status")
def api_status():
    return Response(json.dumps({"token": bool(get_token())}), mimetype="application/json")


@app.route("/api/curl", methods=["POST"])
def api_curl():
    text = (request.form.get("curl") or request.get_json(silent=True) or {}).get("curl", "")
    if isinstance(request.get_json(silent=True), dict) and not text:
        text = request.get_json(silent=True).get("curl", "")
    text = (request.form.get("curl") or "").strip() or text
    if not text:
        return Response(json.dumps({"ok": False, "err": "Curl empty"}), mimetype="application/json")
    t = token_from_text(text)
    if not t:
        return Response(json.dumps({"ok": False, "err": "Curl me token nahi"}), mimetype="application/json")
    with open(CURL_FILE, "w", encoding="utf-8") as f:
        f.write(text)
    return Response(json.dumps({"ok": True, "msg": "Curl updated"}), mimetype="application/json")


@app.route("/api/preview", methods=["POST"])
def api_preview():
    text = (request.form.get("input") or "").strip()
    if not text:
        return Response(json.dumps({"ok": False, "err": "Kuch paste karo"}), mimetype="application/json")
    # all-episodes curl
    ae = parse_all_episodes(text)
    if ae:
        token = get_token()
        if not token:
            return Response(json.dumps({"ok": False, "err": "Token nahi — curl update karo"}), mimetype="application/json")
        try:
            j = fetch_episodes_json(ae[0], ae[1], token)
            eps = parse_episodes_from_json(j)
            return Response(json.dumps({"ok": True, "type": "show", "show": eps[0]["show"] if eps else "Show", "episodes": eps}), mimetype="application/json")
        except RuntimeError as e:
            return Response(json.dumps({"ok": False, "err": str(e)}), mimetype="application/json")
    # raw JSON episodes
    if text.lstrip().startswith("{") and "episodeNumber" in text:
        try:
            eps = parse_episodes_from_json(text)
            return Response(json.dumps({"ok": True, "type": "show", "show": eps[0]["show"] if eps else "Show", "episodes": eps}), mimetype="application/json")
        except Exception as e:
            return Response(json.dumps({"ok": False, "err": f"JSON fail: {e}"}), mimetype="application/json")
    # single movie/episode id or curl
    ids = []
    for part in re.split(r"[\s,;]+", text):
        part = part.strip()
        if not part:
            continue
        r = id_from_curl(part)
        if r:
            if r not in ids:
                ids.append(r)
        elif re.fullmatch(r"[0-9a-f]+", part):
            ids.append((part, "auto"))
    if not ids:
        return Response(json.dumps({"ok": False, "err": "Movie ID nahi mili"}), mimetype="application/json")
    return Response(json.dumps({"ok": True, "type": "ids", "items": [{"id": i, "kind": k} for i, k in ids]}), mimetype="application/json")


@app.route("/api/add", methods=["POST"])
def api_add():
    data = request.form
    text = (data.get("input") or "").strip()
    sel = (data.get("episodes") or "").strip()
    token = get_token()
    if not token:
        return Response(json.dumps({"ok": False, "err": "Token nahi — curl update karo"}), mimetype="application/json")

    # episodes selected (from preview) → add selected only
    if sel:
        eps = []
        for item in sel.split(","):
            item = item.strip()
            if not item:
                continue
            parts = item.split("|")
            eps.append({"id": parts[0], "episode": parts[1] if len(parts) > 1 else "?"})
        if len(eps) > 4:
            return Response(json.dumps({"ok": False, "err": "Max 4 episodes per click. Aur chahiye to dobara click karo."}), mimetype="application/json")
        ok, err = add_episode_batch(eps, token)
        res = {"ok": True, "msg": f"Added {len(ok)} episodes", "ok_list": ok[:4], "err_list": err[:4]}
        return Response(json.dumps(res), mimetype="application/json")

    # normal id(s) / curl add
    ids = []
    for part in re.split(r"[\s,;]+", text):
        part = part.strip()
        if not part:
            continue
        r = id_from_curl(part)
        if r:
            if r not in ids:
                ids.append(r)
        elif re.fullmatch(r"[0-9a-f]+", part):
            ids.append((part, "auto"))
    if not ids:
        return Response(json.dumps({"ok": False, "err": "Movie ID nahi mili"}), mimetype="application/json")
    ok_list, err_list = [], []
    for mid, kind in ids[:4]:
        try:
            done, m = add_movie(mid, token, kind)
            ok_list.append(m)
        except RuntimeError as e:
            err_list.append(f"{mid}: " + {"token_expired": "token expired", "rate_limited": "rate limited (429)"}.get(str(e), str(e)))
        except Exception as e:
            err_list.append(f"{mid}: {e}")
    res = {"ok": bool(ok_list), "msg": " ; ".join(ok_list), "ok_list": ok_list, "err_list": err_list}
    return Response(json.dumps(res), mimetype="application/json")


@app.route("/api/delete", methods=["POST"])
def api_delete():
    mid = (request.form.get("id") or "").strip()
    db = load_db()
    before = len(db)
    db = [x for x in db if x["id"] != mid]
    if len(db) < before:
        save_db(db)
        return Response(json.dumps({"ok": True, "msg": "Deleted"}), mimetype="application/json")
    return Response(json.dumps({"ok": False, "err": "Nahi mili"}), mimetype="application/json")


# --------------------------- M3U + streaming -------------------------------
@app.route("/movies.m3u8")
def playlist():
    db = load_db()
    base = f"http://{request.host}"
    out = ["#EXTM3U"]
    for m in db:
        t = (m.get("title") or m["id"]).replace(",", " ")
        g = (m.get("group") or "Cartoon").replace(",", " ")
        out.append(f'#EXTINF:-1 tvg-id="{m["id"]}" tvg-logo="{m.get("image","")}" group-title="{g}",{t}')
        out.append(f"{base}/stream/{m['id']}/playlist.m3u8")
    return Response("\n".join(out) + "\n", mimetype="application/vnd.apple.mpegurl")


@app.route("/stream/<movie>/playlist.m3u8")
def stream_pl(movie):
    db = load_db()
    m = next((x for x in db if x["id"] == movie), None)
    if not m or not m.get("stream"):
        return "stream nahi hai", 404
    variant = m["stream"]
    try:
        _, body, _ = http_bytes(variant, {"User-Agent": UA, "Referer": "https://kartoons.me/"})
    except Exception:
        return "stream URL expire — add script se dobara add karo", 410
    base = f"http://{request.host}"
    lines = []
    for ln in body.decode("utf-8", "replace").splitlines():
        s = ln.strip()
        if s and not s.startswith("#") and s.startswith("http"):
            lines.append(f"{base}/seg/{movie}?u=" + urllib.parse.quote(s, safe=""))
        else:
            lines.append(ln)
    return Response("\n".join(lines), mimetype="application/vnd.apple.mpegurl")


@app.route("/seg/<movie>")
def seg(movie):
    u = request.args.get("u", "")
    if not u:
        return "no url", 400
    try:
        status, data, ctype = http_bytes(u, {"User-Agent": UA, "Referer": "https://kartoons.me/"})
    except Exception as e:
        return f"seg fail: {e}", 502
    r = Response(data, status=status, mimetype=ctype or "video/mp2t")
    r.headers["Cache-Control"] = "no-store"
    return r


# --------------------------- main -------------------------------
def main():
    args = sys.argv[1:]
    port = 5000
    if "--port" in args:
        port = int(args[args.index("--port") + 1])
    if args and args[0] == "add":
        cmd_add(args[1:])
        return
    if args and args[0] == "reset":
        json.dump([], open(DB_FILE, "w"))
        print("[*] DB reset")
        return
    print("=" * 52)
    print(" 🎬 Kartoons — Netflix style (backend)")
    print(f"   UI:   http://localhost:{port}/")
    print(f"   VLC:  vlc http://localhost:{port}/movies.m3u8")
    print(f"   CLI:  python3 kartoons.py add <id>")
    print("=" * 52)
    app.run(host="0.0.0.0", port=port, threaded=True)


if __name__ == "__main__":
    main()