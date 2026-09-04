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
PAGE = '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width,initial-scale=1">\n<title>NepToons — Streaming</title>\n\n<style>*{box-sizing:border-box;margin:0;padding:0}\nbody{background:#0d0d16;color:#fff;font-family:\'Inter\',\'Segoe UI\',system-ui,sans-serif}\na{text-decoration:none;color:inherit}\nbutton{font-family:inherit}\n\n/* ===== Header ===== */\n.nav{position:fixed;top:0;left:0;right:0;z-index:99;display:flex;align-items:center;gap:18px;padding:14px 3.5%;background:linear-gradient(#000,rgba(0,0,0,.6),transparent);transition:.3s;backdrop-filter:blur(0px)}\n.nav.solid{background:rgba(13,13,22,.82);backdrop-filter:blur(14px);box-shadow:0 2px 20px rgba(0,0,0,.4)}\n.menu-btn{background:none;border:0;color:#fff;font-size:20px;cursor:pointer;padding:4px;line-height:1}\n.brand{font-size:23px;font-weight:900;letter-spacing:.5px;\n  background:linear-gradient(90deg,#4d9fff,#7f5fff);\n  -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}\n.brand b{-webkit-text-fill-color:#fff}\n.nav-sep{flex:1}\n.search-wrap{position:relative}\n.search-wrap input{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.14);border-radius:22px;padding:8px 14px 8px 36px;color:#fff;width:200px;outline:none;transition:.25s}\n.search-wrap input:focus{width:260px;border-color:#4d9fff;background:rgba(255,255,255,.12)}\n.search-wrap .ic{position:absolute;left:12px;top:50%;transform:translateY(-50%);color:#9aa;pointer-events:none}\n.icon-btn{background:none;border:0;color:#ddd;font-size:18px;cursor:pointer;width:40px;height:40px;border-radius:50%;display:flex;align-items:center;justify-content:center;transition:.2s}\n.icon-btn:hover{background:rgba(255,255,255,.12);color:#fff}\n.avatar{width:34px;height:34px;border-radius:50%;background:linear-gradient(135deg,#4d9fff,#7f5fff);display:flex;align-items:center;justify-content:center;font-weight:800;font-size:15px;cursor:pointer}\n.bell{position:relative}\n.bell::after{content:\'\';position:absolute;top:8px;right:9px;width:7px;height:7px;border-radius:50%;background:#ff4d6d}\n\n/* ===== Alert banner ===== */\n.alert{position:fixed;top:60px;left:0;right:0;z-index:98;display:flex;align-items:center;gap:10px;\n  background:rgba(77,159,255,.14);border-bottom:1px solid rgba(77,159,255,.3);\n  padding:9px 3.5%;font-size:13px;color:#cfd8ff;backdrop-filter:blur(8px)}\n.alert button{background:none;border:0;color:#9aa;font-size:16px;cursor:pointer;margin-left:auto}\n\n/* ===== Hero ===== */\n.hero{height:78vh;min-height:440px;background-size:cover;background-position:center 22%;display:flex;align-items:flex-end;padding:0 3.5% 7%;position:relative}\n.hero::after{content:\'\';position:absolute;inset:0;background:linear-gradient(90deg,rgba(10,10,18,.95) 0%,rgba(10,10,18,.65) 45%,rgba(10,10,18,.25) 70%,rgba(10,10,18,.9) 100%),linear-gradient(transparent 40%,#0d0d16 98%)}\n.hero-box{position:relative;z-index:2;max-width:600px;animation:fadein .6s ease}\n@keyframes fadein{from{opacity:0;transform:translateY(18px)}to{opacity:1;transform:none}}\n.hero h1{font-size:52px;font-weight:900;line-height:1.05;letter-spacing:-.5px;\n  text-shadow:0 4px 30px rgba(0,0,0,.8)}\n.gtags{display:flex;gap:8px;margin:16px 0 10px;flex-wrap:wrap}\n.gtag{background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.2);padding:4px 14px;border-radius:20px;font-size:12px;font-weight:600;backdrop-filter:blur(6px)}\n.hero-meta{color:#c9ccd9;font-size:14px;margin-bottom:12px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}\n.hero-meta .rt{color:#ffd75e;font-weight:700}\n.hero-meta .dot{color:#555}\n.hero .desc{color:#cfd2df;font-size:15px;line-height:1.55;margin-bottom:22px;max-width:540px}\n.hbtns{display:flex;gap:12px}\n.hbtn{border:0;border-radius:12px;font-size:16px;font-weight:700;padding:13px 28px;cursor:pointer;display:flex;align-items:center;gap:9px;transition:.2s}\n.hbtn.blue{background:linear-gradient(135deg,#3b82f6,#2563eb);color:#fff;box-shadow:0 6px 24px rgba(59,130,246,.45)}\n.hbtn.blue:hover{transform:translateY(-2px);box-shadow:0 10px 30px rgba(59,130,246,.55)}\n.hbtn.glass{background:rgba(255,255,255,.12);color:#fff;backdrop-filter:blur(12px);border:1px solid rgba(255,255,255,.18)}\n.hbtn.glass:hover{background:rgba(255,255,255,.2)}\n.hero-dots{position:absolute;right:3.5%;bottom:6%;z-index:3;display:flex;gap:8px}\n.dot{width:9px;height:9px;border-radius:50%;background:rgba(255,255,255,.3);cursor:pointer;transition:.2s}\n.dot.on{background:#4d9fff;transform:scale(1.25)}\n\n/* ===== Rows ===== */\n.row{padding:22px 3.5%}\n.row h2{font-size:19px;font-weight:700;margin-bottom:14px;display:flex;align-items:center;gap:8px}\n.row h2::after{content:\'\';flex:1;height:1px;background:linear-gradient(90deg,rgba(255,255,255,.12),transparent)}\n.hscroll{display:flex;gap:14px;overflow-x:auto;padding-bottom:10px;scrollbar-width:thin;scrollbar-color:#3a3a4a transparent}\n.hscroll::-webkit-scrollbar{height:6px}\n.hscroll::-webkit-scrollbar-thumb{background:#3a3a4a;border-radius:3px}\n.card{flex:0 0 215px;width:215px;background:#15151f;border:1px solid #22222f;border-radius:14px;overflow:hidden;cursor:pointer;position:relative;transition:transform .2s,box-shadow .2s}\n.card:hover{transform:translateY(-4px) scale(1.02);box-shadow:0 12px 30px rgba(0,0,0,.5);border-color:#3a3a50}\n.thumb{height:125px;background-size:cover;background-position:center;position:relative}\n.thumb::after{content:\'\';position:absolute;inset:0;background:linear-gradient(transparent 55%,rgba(0,0,0,.7))}\n.playbtn{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:52px;height:52px;border-radius:50%;background:rgba(13,13,22,.65);border:2px solid rgba(255,255,255,.9);color:#fff;font-size:19px;cursor:pointer;z-index:2;opacity:0;transition:.2s;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(4px)}\n.card:hover .playbtn{opacity:1}\n.card:hover .playbtn:hover{background:#3b82f6;border-color:#3b82f6}\n.meta{padding:11px 12px}\n.tt{font-size:14px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}\n.sub{color:#8a8a9a;font-size:12px;margin-top:4px}\n.ep-badge{position:absolute;top:9px;left:9px;z-index:2;background:linear-gradient(135deg,#3b82f6,#7f5fff);color:#fff;font-size:10px;font-weight:800;padding:3px 9px;border-radius:6px;letter-spacing:1px}\n.cont-prog{position:absolute;bottom:0;left:0;height:5px;background:linear-gradient(90deg,#3b82f6,#7f5fff);z-index:3;box-shadow:0 0 8px rgba(59,130,246,.6)}\n\n/* ===== Watch player ===== */\n.wtop{position:fixed;top:0;left:0;right:0;z-index:30;display:flex;align-items:center;gap:16px;padding:16px 2.5%;background:linear-gradient(#000,transparent)}\n.wtop .b2{background:none;border:0;color:#fff;font-size:20px;cursor:pointer}\n.wtop .title{font-size:15px;font-weight:600;color:#eef}\n.wtop .right{margin-left:auto;display:flex;align-items:center;gap:6px}\n.badge4k{background:rgba(77,159,255,.25);color:#8cc4ff;font-size:11px;font-weight:800;padding:3px 9px;border-radius:6px;border:1px solid rgba(77,159,255,.4)}\n.pwrap{background:#000;width:100vw;height:100vh;position:fixed;inset:0;z-index:20}\n.pwrap video{width:100%;height:100%;object-fit:contain;background:#000;display:block}\n.grad{position:absolute;inset:0;pointer-events:none;\n  background:linear-gradient(transparent 40%,rgba(0,0,0,.85) 98%),linear-gradient(rgba(0,0,0,.5),transparent 30%)}\n.paused-label{position:absolute;top:14px;left:2.5%;z-index:25;color:#fff;font-size:13px;font-weight:600;letter-spacing:.3px}\n.bigbtns{position:absolute;top:50%;left:0;right:0;transform:translateY(-50%);z-index:26;display:flex;justify-content:center;gap:40px;align-items:center}\n.bigbtn{background:none;border:0;color:#fff;cursor:pointer;opacity:.95;transition:.2s;display:flex;align-items:center;justify-content:center}\n.bigbtn:hover{opacity:1;transform:scale(1.1)}\n.bigbtn.play{width:92px;height:92px;border-radius:50%;background:rgba(13,13,22,.45);backdrop-filter:blur(6px);border:2px solid rgba(255,255,255,.85);font-size:40px}\n.bigbtn.skip{width:60px;height:60px;border-radius:50%;background:rgba(13,13,22,.4);backdrop-filter:blur(6px);border:1px solid rgba(255,255,255,.5);font-size:24px}\n.bigbtn.skip.l{transform:scaleX(-1)}\n/* settings dropdown */\n.panel{position:absolute;right:2.5%;bottom:78px;z-index:27;min-width:230px;\n  background:rgba(18,18,28,.75);border:1px solid rgba(255,255,255,.12);border-radius:14px;\n  padding:8px;backdrop-filter:blur(20px);box-shadow:0 10px 40px rgba(0,0,0,.6)}\n.pitem{display:flex;align-items:center;gap:12px;padding:11px 14px;border-radius:9px;cursor:pointer;color:#e8e8f0;font-size:14px;transition:.15s}\n.pitem:hover{background:rgba(255,255,255,.1)}\n.pitem.on{background:rgba(77,159,255,.22);color:#fff}\n.pitem .lbl{margin-left:auto;color:#9aa;font-size:13px}\n.pitem .ico{font-size:16px;width:20px;text-align:center}\n/* bottom controls */\n.controls{position:absolute;left:0;right:0;bottom:0;z-index:24;padding:70px 2.5% 22px;\n  display:flex;flex-direction:column;gap:10px;opacity:0;transition:opacity .3s}\n.pwrap.playing .controls,.pwrap:hover .controls{opacity:1}\n.pbar{height:5px;background:rgba(255,255,255,.22);border-radius:3px;cursor:pointer;position:relative}\n.pbar:hover{height:7px}\n.pbar .fill{position:absolute;left:0;top:0;height:100%;background:#4d9fff;border-radius:3px;z-index:2}\n.pbar .buff{position:absolute;left:0;top:0;height:100%;background:rgba(255,255,255,.35);border-radius:3px}\n.pbar .knob{position:absolute;top:50%;transform:translate(-50%,-50%);width:15px;height:15px;border-radius:50%;background:#fff;box-shadow:0 0 10px rgba(77,159,255,.8);z-index:3;opacity:0;transition:.2s}\n.pbar:hover .knob{opacity:1}\n.crow{display:flex;align-items:center;gap:16px}\n.cbtn{background:none;border:0;color:#fff;font-size:22px;cursor:pointer;line-height:1;opacity:.95;transition:.2s}\n.cbtn:hover{opacity:1;transform:scale(1.08)}\n.cbtn.small{font-size:19px}\n.time{font-size:13px;color:#cfd2df;font-variant-numeric:tabular-nums;letter-spacing:.3px}\n.sp{flex:1}\n/* volume capsule */\n.volwrap{display:flex;align-items:center;gap:8px}\n.vcap{display:flex;align-items:center;gap:8px;background:rgba(255,255,255,.12);border-radius:20px;padding:4px 6px 4px 8px;backdrop-filter:blur(6px)}\n.vcap input[type=range]{width:80px;accent-color:#4d9fff;height:4px}\n\n/* ===== Info page ===== */\n.info{max-width:1100px;margin:96vh auto 0;padding:24px 4% 40px;position:relative;z-index:5}\n.info h1{font-size:32px;font-weight:900;margin:0 0 10px}\n.hero-meta2{color:#c9ccd9;font-size:14px;margin-bottom:14px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}\n.hero-meta2 .rt{color:#ffd75e;font-weight:700}\nimg.poster{float:right;width:150px;border-radius:12px;margin-left:18px;box-shadow:0 8px 30px rgba(0,0,0,.6)}\n.desc{color:#cfd2df;line-height:1.65;max-width:720px}\n.actions{display:flex;gap:12px;margin-top:18px}\n.ab{background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.15);color:#fff;font-weight:700;padding:10px 22px;border-radius:10px;cursor:pointer;font-size:15px;transition:.2s;backdrop-filter:blur(8px)}\n.ab:hover{background:rgba(255,255,255,.18)}\n.ab.blue{background:linear-gradient(135deg,#3b82f6,#2563eb);border:0;box-shadow:0 6px 20px rgba(59,130,246,.4)}\n.ep{display:inline-block;background:linear-gradient(135deg,#3b82f6,#7f5fff);color:#fff;font-weight:800;font-size:13px;padding:4px 13px;border-radius:7px;margin-bottom:12px}\n.more h2{font-size:18px;margin:26px 0 12px}\n.btns-right{display:flex;gap:10px;justify-content:flex-end;padding:14px 3.5% 0;position:relative;z-index:6}\n.btns-right button{background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.15);color:#fff;padding:9px 18px;border-radius:9px;cursor:pointer;font-weight:600;transition:.2s}\n.btns-right button:hover{background:rgba(255,255,255,.2)}\n\n/* ===== Modal ===== */\n.overlay{position:fixed;inset:0;z-index:200;background:rgba(8,8,14,.85);display:flex;align-items:center;justify-content:center;backdrop-filter:blur(8px)}\n.modal{width:92%;max-width:720px;max-height:90vh;overflow-y:auto;background:#16161f;border-radius:18px;padding:26px;border:1px solid #2a2a3a;box-shadow:0 20px 60px rgba(0,0,0,.7)}\n.modal h2{font-size:23px;margin-bottom:18px;display:flex;align-items:center;gap:8px}\ntextarea{width:100%;background:#0d0d16;border:1px solid #2a2a3a;border-radius:10px;color:#fff;padding:12px;font-size:13px;margin-bottom:12px;font-family:monospace;outline:none;transition:.2s}\ntextarea:focus{border-color:#4d9fff}\n#curlbox{height:70px}\n#addbox{height:90px}\n.modal button{background:linear-gradient(135deg,#3b82f6,#2563eb);color:#fff;border:0;border-radius:10px;padding:10px 22px;font-size:14px;font-weight:700;cursor:pointer;margin-right:8px;transition:.2s}\n.modal button:hover{transform:translateY(-1px);box-shadow:0 6px 20px rgba(59,130,246,.4)}\n.modal button.gray{background:#333}\n.modal button.tiny{background:#333;padding:5px 12px;font-size:12px}\n.tok{display:inline-block;padding:6px 14px;border-radius:20px;font-size:13px;font-weight:700;margin-left:10px}\n.tok.g{background:rgba(70,211,105,.15);color:#46d369;border:1px solid rgba(70,211,105,.3)}\n.tok.r{background:rgba(255,77,109,.15);color:#ff6b6b;border:1px solid rgba(255,77,109,.3)}\n.msg{background:rgba(70,211,105,.12);border:1px solid rgba(70,211,105,.3);color:#46d369;padding:11px;border-radius:10px;margin-bottom:12px}\n.msg.err{background:rgba(255,77,109,.12);border-color:rgba(255,77,109,.3);color:#ff6b6b}\n.epsel{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}\n.epsel label{background:#2a2a3a;padding:8px 13px;border-radius:8px;cursor:pointer;font-size:13px;user-select:none;transition:.2s;border:1px solid transparent}\n.epsel input{display:none}\n.epsel label.on{background:linear-gradient(135deg,#3b82f6,#7f5fff);border-color:#fff}\n.libh{display:flex;align-items:center;gap:12px;margin:20px 0 12px}\n.libh h3{font-size:18px}\n.lib{display:flex;flex-direction:column;gap:8px}\n.lcard{display:flex;align-items:center;gap:12px;background:#1a1a24;border:1px solid #2a2a3a;border-radius:12px;padding:8px;transition:.2s}\n.lcard:hover{border-color:#4d9fff}\n.lcard img{width:58px;height:80px;object-fit:cover;border-radius:8px}\n.lcard .linfo{flex:1}\n.lcard .sub{color:#8a8a9a;font-size:12px}\n.lcard button{background:transparent;color:#ff6b6b;font-size:18px;padding:4px 8px}\n.pad{height:70px}\n.hid{display:none}\n</style>\n</head>\n<body>\n<header class="nav" id="nav">\n  <button class="menu-btn" onclick="showHome()">☰</button>\n  <div class="brand">Nep<b>Toons</b></div>\n  <div class="nav-sep"></div>\n  <div class="search-wrap">\n    <span class="ic">🔍</span>\n    <input id="q" placeholder="Search..." oninput="renderHome()">\n  </div>\n  <button class="icon-btn bell" onclick="openAdd()">🔔</button>\n  <button class="icon-btn" onclick="openAdd()">+ Add</button>\n  <div class="avatar" onclick="openAdd()">N</div>\n</header>\n\n<div class="alert" id="alert">\n  <span>⚡ Due to an increase in traffic, we are experiencing some issues. We are working on fixing them.</span>\n  <button onclick="document.getElementById(\'alert\').remove()">✕</button>\n</div>\n\n<!-- HOME VIEW -->\n<div id="home">\n  <div class="hero" id="hero"></div>\n  <div id="rows"></div>\n  <div class="pad"></div>\n</div>\n\n<!-- WATCH VIEW -->\n<div id="watch" class="hid">\n  <div class="wtop">\n    <button class="b2" onclick="showHome()">←</button>\n    <span class="title" id="wtitle">Loading...</span>\n    <div class="right">\n      <span class="badge4k">4K</span>\n      <button class="b2" onclick="togglePanel()">⚙️</button>\n    </div>\n  </div>\n  <div class="pwrap" id="pwrap">\n    <video id="v"></video>\n    <div class="grad"></div>\n    <div class="paused-label" id="plabel">Paused</div>\n    <div class="bigbtns" id="bigbtns">\n      <button class="bigbtn skip l" id="bback">⏭</button>\n      <button class="bigbtn play" id="big">▶</button>\n      <button class="bigbtn skip" id="bfwd">⏭</button>\n    </div>\n    <div class="panel hid" id="panel">\n      <div class="pitem"><span class="ico">⏷</span> Subtitle Settings</div>\n      <div class="pitem"><span class="ico">⏱</span> Speed<span class="lbl">1x</span></div>\n      <div class="pitem on"><span class="ico">⬒</span> Aspect<span class="lbl">Original</span></div>\n      <div class="pitem"><span class="ico">🔁</span> Loop<span class="lbl">Off</span></div>\n    </div>\n    <div class="controls" id="ctl">\n      <div class="pbar" id="pbar"><div class="buff" id="buff"></div><div class="fill" id="fill"></div><div class="knob" id="knob"></div></div>\n      <div class="crow">\n        <button class="cbtn" id="play">⏸</button>\n        <span class="time" id="time">0:00 / 0:00</span>\n        <div class="volwrap">\n          <button class="cbtn small" id="vol">🔊</button>\n          <div class="vcap"><input type="range" id="vslider" min="0" max="100" value="100"></div>\n        </div>\n        <span class="sp"></span>\n        <button class="cbtn small" id="back">⏪ 10</button>\n        <button class="cbtn small" id="fwd">10 ⏩</button>\n        <button class="cbtn" id="full">⛶</button>\n      </div>\n    </div>\n  </div>\n  <div class="info" id="winfo"></div>\n  <div class="more info" id="wmore"></div>\n</div>\n\n<!-- ADD MODAL -->\n<div class="overlay hid" id="overlay" onclick="if(event.target===this)closeAdd()">\n  <div class="modal">\n    <h2>➕ Add Movies / Show</h2>\n    <div class="curlbox">\n      <textarea id="curlbox" placeholder="Yahan naya curl paste karke Update dabao (token save)"></textarea>\n      <button class="gray" onclick="updateCurl()">💾 Update Curl</button>\n      <span class="tok hid" id="tok"></span>\n    </div>\n    <textarea id="addbox" placeholder="Movie ID, curl, ya poora show ka all-episodes curl/JSON paste karo..."></textarea>\n    <button onclick="preview()">🔍 Preview</button>\n    <div id="pv"></div>\n    <div class="libh"><h3>🎞️ Library</h3><button class="tiny" onclick="refresh()">Refresh</button></div>\n    <div id="lib" class="lib"></div>\n  </div>\n</div>\n\n<script src="https://cdn.jsdelivr.net/npm/hls.js@1/dist/hls.min.js"></script>\n<script>// ==================== NepToons — Streamio-style SPA ====================\nvar DB = [];\nvar TOKEN = false;\nvar heroTimer = null, heroIdx = 0;\nvar hls = null;\nvar currentItem = null;\nvar lastSaved = 0;\n\n// ---------- playback progress (resume) in localStorage ----------\nfunction getProg(id) {\n  try { return JSON.parse(localStorage.getItem("nt_prog_" + id) || "null"); }\n  catch (e) { return null; }\n}\nfunction setProg(id, pos, dur) {\n  try {\n    const p = getProg(id) || {};\n    p.pos = pos; p.dur = dur; p.ts = Date.now();\n    localStorage.setItem("nt_prog_" + id, JSON.stringify(p));\n  } catch (e) {}\n}\n\nasync function jf(url, opts) {\n  const r = await fetch(url, opts);\n  return r.json();\n}\nasync function post(url, body) {\n  const fd = new FormData();\n  for (const k in body) fd.append(k, body[k]);\n  return jf(url, { method: "POST", body: fd });\n}\n\nasync function refresh() {\n  DB = await jf("/api/movies");\n  TOKEN = (await jf("/api/status")).token;\n  const t = document.getElementById("tok");\n  if (t) {\n    t.classList.remove("hid");\n    t.textContent = TOKEN ? "✅ Token OK" : "❌ No token";\n    t.className = "tok " + (TOKEN ? "g" : "r");\n  }\n}\n\nfunction pct(m) {\n  const p = getProg(m.id);\n  if (!p || !p.dur || p.dur < 1) return 0;\n  return Math.min(100, Math.round(p.pos / p.dur * 100));\n}\nfunction resumeLabel(m) {\n  const p = getProg(m.id);\n  if (!p || !p.pos || p.pos < 5) return null;\n  return p;\n}\n\nfunction cardHTML(m) {\n  const badge = m.kind === "episode" ? \'<span class="ep-badge">EP</span>\' : "";\n  const yr = m.year || "", rt = m.rating;\n  const rts = rt != null ? `★ ${rt}` : "";\n  const prog = pct(m);\n  const resume = resumeLabel(m);\n  const btnLabel = resume ? "▶ Resume" : "▶ Start";\n  const progBar = prog > 0 ? `<div class="cont-prog" style="width:${prog}%"></div>` : "";\n  return `<div class="card" onclick="openWatch(\'${m.id}\')">\n    <div class="thumb" style="background-image:url(\'${m.image||""}\')">${badge}${progBar}\n      <button class="playbtn" onclick="event.stopPropagation();openWatch(\'${m.id}\')">${btnLabel}</button>\n    </div>\n    <div class="meta"><div class="tt">${m.title||""}</div><div class="sub">${rts} ${yr}${resume?` · ${Math.floor(resume.pos/60)}:${String(Math.floor(resume.pos%60)).padStart(2,\'0\')}`:""}</div></div>\n  </div>`;\n}\n\nfunction rowHTML(title, items) {\n  if (!items || !items.length) return "";\n  const cards = items.map(cardHTML).join("");\n  return `<div class="row"><h2>${title}</h2><div class="hscroll">${cards}</div></div>`;\n}\n\n// ---------- homepage rendering (optimized) ----------\nfunction renderHome() {\n  const q = (document.getElementById("q").value || "").trim().toLowerCase();\n  const list = q ? DB.filter(m => (m.title||"").toLowerCase().includes(q)) : DB;\n  const heroEl = document.getElementById("hero");\n  const rowsEl = document.getElementById("rows");\n  const visible = q ? list : DB;\n  if (!q) {\n    if (visible.length) { renderHero(visible); heroEl.style.display = "flex"; }\n    else heroEl.style.display = "none";\n  } else {\n    heroEl.style.display = "none";\n    clearInterval(heroTimer);\n  }\n  let html = "";\n  if (q) {\n    html = rowHTML("Search Results", visible);\n  } else {\n    // Continue watching row (has progress)\n    const cw = visible.filter(m => resumeLabel(m));\n    if (cw.length) html += rowHTML("▶ Continue Watching", cw);\n    html += rowHTML("Trending Now", visible);\n    const groups = {};\n    visible.forEach(m => { const g = m.group || "Movies"; (groups[g] = groups[g] || []).push(m); });\n    for (const g in groups) html += rowHTML(g, groups[g]);\n    const eps = visible.filter(m => m.kind === "episode");\n    if (eps.length) html += rowHTML("Episodes", eps);\n    const movies = visible.filter(m => m.kind !== "episode");\n    if (movies.length) html += rowHTML("Movies", movies);\n  }\n  rowsEl.innerHTML = html;\n}\n\nfunction renderHero(list) {\n  const hero = document.getElementById("hero");\n  heroIdx = 0;\n  clearInterval(heroTimer);\n  const show = (i) => {\n    const m = list[i % list.length];\n    const tags = (m.tags||[]).slice(0,3).map(t=>`<span class="gtag">${t}</span>`).join("");\n    hero.style.backgroundImage = `url(\'${m.image||""}\')`;\n    const type = m.kind === "episode" ? "Episode" : "Movie";\n    const resume = resumeLabel(m);\n    const btnLabel = resume ? "▶ Resume" : "▶ Watch Now";\n    hero.innerHTML = `<div class="hero-box">\n      <h1>${m.title||""}</h1>\n      <div class="gtags">${tags}</div>\n      <div class="hero-meta">\n        <span>${type}</span><span class="dot">•</span>\n        <span>${m.year||""}</span><span class="dot">•</span>\n        <span class="rt">★ ${m.rating||""}</span>${m.duration?`<span class="dot">•</span><span>${m.duration} min</span>`:""}\n      </div>\n      <p class="desc">${(m.description||"").slice(0,230)}</p>\n      <div class="hbtns">\n        <button class="hbtn blue" onclick="openWatch(\'${m.id}\')">${btnLabel}</button>\n        <button class="hbtn glass" onclick="openAdd()">ℹ More Info</button>\n      </div>\n    </div>\n    <div class="hero-dots">${list.map((_,x)=>`<span class="dot ${x===i%list.length?\'on\':\'\'}" onclick="show(${x});clearInterval(heroTimer);startHero()"></span>`).join("")}</div>`;\n  };\n  show(0);\n  startHero = () => { clearInterval(heroTimer); heroTimer = setInterval(() => show(++heroIdx), 7000); };\n  startHero();\n}\nvar startHero = null;\n\nfunction showHome() {\n  document.getElementById("home").classList.remove("hid");\n  document.getElementById("watch").classList.add("hid");\n  if (hls) { hls.destroy(); hls = null; }\n  document.title = "NepToons — Streaming";\n  renderHome();\n}\n\n// ==================== Player ====================\nfunction openWatch(id) {\n  const m = DB.find(x => x.id === id);\n  if (!m) return;\n  currentItem = m;\n  document.getElementById("home").classList.add("hid");\n  document.getElementById("watch").classList.remove("hid");\n  const src = `/stream/${id}/playlist.m3u8`;\n  const video = document.getElementById("v");\n  const big = document.getElementById("big");\n  const pwrap = document.getElementById("pwrap");\n  const play = document.getElementById("play");\n  const time = document.getElementById("time");\n  const fill = document.getElementById("fill");\n  const knob = document.getElementById("knob");\n  const buff = document.getElementById("buff");\n  const pbar = document.getElementById("pbar");\n  const vslider = document.getElementById("vslider");\n  const plabel = document.getElementById("plabel");\n  document.getElementById("wtitle").textContent = m.title||"";\n\n  const tags = (m.tags||[]).map(t=>`<span class="gtag">${t}</span>`).join("");\n  const ep = m.episode ? `<div class="ep">📺 ${m.episode}</div>` : "";\n  const resume = resumeLabel(m);\n  document.getElementById("winfo").innerHTML = `\n    <img class="poster" src="${m.image||""}">\n    ${ep}<h1>${m.title||""}</h1>\n    <div class="hero-meta2"><span class="rt">★ ${m.rating||""}</span> · ${m.year||""} · ${m.duration||""} min · ${tags}</div>\n    <p class="desc">${m.description||""}</p>\n    <div class="actions">\n      <button class="ab blue" onclick="document.getElementById(\'v\').play();pwrap.classList.add(\'playing\')">▶ ${resume?\'Resume\':\'Play\'}</button>\n      <button class="ab" onclick="showHome()">🏠 Home</button>\n      <button class="ab" onclick="openAdd()">➕ Add More</button>\n    </div>`;\n  const others = DB.filter(x => x.id !== id);\n  document.getElementById("wmore").innerHTML = others.length ? `<h2>More Like This</h2><div class="hscroll">${others.map(cardHTML).join("")}</div>` : "";\n  document.title = (m.title||"") + " — NepToons";\n\n  if (hls) hls.destroy();\n  function fmt(s){s=Math.floor(s||0);var m=Math.floor(s/60);return m+\':\'+String(s%60).padStart(2,\'0\')}\n  function upd(){\n    if (!video.duration) return;\n    const p = video.currentTime/video.duration*100;\n    fill.style.width = p+\'%\';\n    knob.style.left = p+\'%\';\n    time.textContent = fmt(video.currentTime)+\' / \'+fmt(video.duration);\n    // save resume (throttled ~2s)\n    const now = Date.now();\n    if (now - lastSaved > 2000 && video.currentTime > 5) {\n      setProg(id, video.currentTime, video.duration);\n      lastSaved = now;\n    }\n  }\n  video.removeEventListener(\'timeupdate\',upd);\n  video.addEventListener(\'timeupdate\',upd);\n\n  function setPlayState(){\n    play.textContent = video.paused ? \'▶\' : \'⏸\';\n    big.style.display = video.paused ? \'flex\' : \'none\';\n    plabel.textContent = video.paused ? (m.kind===\'episode\'?\'Episode\':\'Paused\') : \'Playing\';\n  }\n  function tog(){\n    if (video.paused) { video.play().catch(function(){}); }\n    else { video.pause(); }\n    setPlayState();\n  }\n\n  // -------- FIXED pause: video click + big button + play button all toggle --------\n  play.onclick = tog;\n  big.onclick = tog;\n  video.onclick = tog;      // <-- was missing, caused "pause not working"\n  video.ondblclick = function(){ if(document.fullscreenElement)document.exitFullscreen(); else document.querySelector(\'.pwrap\').requestFullscreen(); };\n  document.getElementById(\'bback\').onclick=()=>{video.currentTime-=10;showCtl()};\n  document.getElementById(\'bfwd\').onclick=()=>{video.currentTime+=10;showCtl()};\n  document.getElementById(\'back\').onclick=()=>{video.currentTime-=10;showCtl()};\n  document.getElementById(\'fwd\').onclick=()=>{video.currentTime+=10;showCtl()};\n  document.getElementById(\'full\').onclick=()=>{if(document.fullscreenElement)document.exitFullscreen();else document.querySelector(\'.pwrap\').requestFullscreen()};\n  document.getElementById(\'vol\').onclick=function(){video.muted=!video.muted;this.textContent=video.muted?\'🔇\':\'🔊\';vslider.value=video.muted?0:video.volume*100;showCtl()};\n  vslider.oninput=function(){video.volume=this.value/100;video.muted=false;document.getElementById(\'vol\').textContent=video.volume?\'🔊\':\'🔇\';showCtl()};\n  pbar.onclick=function(e){var r=pbar.getBoundingClientRect();video.currentTime=(e.clientX-r.left)/r.width*video.duration;showCtl()};\n  video.addEventListener(\'progress\',function(){if(video.buffered&&video.buffered.length){var b=video.buffered.end(video.buffered.length-1);buff.style.width=(b/video.duration*100)+\'%\';}});\n  video.addEventListener(\'play\',()=>setPlayState());\n  video.addEventListener(\'pause\',()=>setPlayState());\n  video.addEventListener(\'ended\',()=>{setPlayState(); setProg(id,0,0);});\n  video.volume = vslider.value/100;\n\n  // autohide controls\n  let hideT=null;\n  function showCtl(){\n    pwrap.classList.add(\'playing\');\n    plabel.style.opacity=\'1\';\n    clearTimeout(hideT);\n    hideT=setTimeout(()=>{ if(!video.paused){ pwrap.classList.remove(\'playing\'); plabel.style.opacity=\'0\'; } },2800);\n  }\n  showCtl();\n  pwrap.onmousemove=showCtl;\n\n  video.muted=false;\n  if (window.Hls && Hls.isSupported()) {\n    hls = new Hls({maxBufferLength:60,enableWorker:true,lowLatencyMode:false});\n    hls.loadSource(src);hls.attachMedia(video);\n    hls.on(Hls.Events.MANIFEST_PARSED,()=>{\n      // resume from saved position\n      const r = getProg(id);\n      if (r && r.pos && r.pos > 5 && r.pos < (r.dur||999999) - 10) {\n        try { video.currentTime = r.pos; } catch(e){}\n      }\n      video.play().then(()=>{big.style.display=\'none\';play.textContent=\'⏸\';setPlayState();}).catch(()=>{});\n    });\n    hls.on(Hls.Events.ERROR,(e,d)=>{if(d&&d.fatal){if(d.type==="networkError")setTimeout(()=>hls.startLoad(),2000);else hls.recoverMediaError()}});\n  } else if (video.canPlayType("application/vnd.apple.mpegurl")) {\n    video.src=src;\n    const r = getProg(id);\n    video.onloadedmetadata=function(){ if(r&&r.pos&&r.pos>5){try{video.currentTime=r.pos;}catch(e){}} };\n    video.play();\n  }\n  // keyboard\n  document.onkeydown=function(e){\n    if(!currentItem) return;\n    if(e.code===\'Space\'){e.preventDefault();tog();}\n    else if(e.key===\'ArrowRight\'){video.currentTime+=10;showCtl();}\n    else if(e.key===\'ArrowLeft\'){video.currentTime-=10;showCtl();}\n    else if(e.key===\'f\'||e.key===\'F\'){if(document.fullscreenElement)document.exitFullscreen();else document.querySelector(\'.pwrap\').requestFullscreen();}\n  };\n  window.scrollTo(0,0);\n}\n\nfunction togglePanel(){ document.getElementById(\'panel\').classList.toggle(\'hid\'); }\n\n// ---------- add modal ----------\nfunction openAdd() {\n  document.getElementById("overlay").classList.remove("hid");\n  refresh().then(() => renderLib());\n}\nfunction closeAdd() { document.getElementById("overlay").classList.add("hid"); }\nfunction msg(html, err) { document.getElementById("pv").innerHTML = `<div class="msg ${err?\'err\':\'\'}">${html}</div>`; }\n\nasync function updateCurl() {\n  const t = document.getElementById("curlbox").value;\n  if (!t) return msg("Curl empty", true);\n  const r = await post("/api/curl", { curl: t });\n  msg(r.ok ? "✅ " + r.msg : "⚠️ " + r.err, !r.ok);\n  refresh();\n}\n\nvar previewData = null;\nasync function preview() {\n  const t = document.getElementById("addbox").value;\n  if (!t) return msg("Kuch paste karo", true);\n  const r = await post("/api/preview", { input: t });\n  if (!r.ok) return msg("⚠️ " + r.err, true);\n  if (r.type === "show") {\n    previewData = r.episodes;\n    const labels = r.episodes.map(e=>`<label onclick="this.classList.toggle(\'on\');this.querySelector(\'input\').checked=!this.querySelector(\'input\').checked"><input type="checkbox" value="${e.id}|${e.episode}">${e.episode}</label>`).join("");\n    msg(`🎬 <b>${r.show}</b> — ${r.episodes.length} episodes. Select up to 4 → Add.`, false);\n    document.getElementById("pv").insertAdjacentHTML(\'beforeend\', `<div class="epsel" id="epsel">${labels}</div><button onclick="addSelected()">⚡ Add Selected (max 4)</button>`);\n  } else {\n    previewData = null;\n    msg(`✅ Found ${r.items.length} item(s). Click Add below.`, false);\n    document.getElementById("pv").insertAdjacentHTML(\'beforeend\', `<br><button onclick="addRaw()">⚡ Add ${r.items.length}</button>`);\n  }\n}\n\nasync function addSelected() {\n  const sel = [...document.querySelectorAll(\'#epsel input:checked\')].map(i => i.value);\n  if (!sel.length) return msg("Koi episode select nahi kiya", true);\n  if (sel.length > 4) return msg("Max 4 episodes per click", true);\n  msg("Adding... ⏳", false);\n  const r = await post("/api/add", { episodes: sel.join(",") });\n  const text = r.ok ? `✅ ${r.msg}: ${(r.ok_list||[]).join(", ")}` : "⚠️ " + (r.err||"");\n  msg(text, !r.ok);\n  if (r.err_list && r.err_list.length) document.getElementById("pv").insertAdjacentHTML("beforeend", `<div class="msg err">⚠️ ${r.err_list.join("<br>")}</div>`);\n  refresh(); renderLib();\n}\n\nasync function addRaw() {\n  const t = document.getElementById("addbox").value;\n  msg("Adding... ⏳", false);\n  const r = await post("/api/add", { input: t });\n  msg(r.ok ? "✅ " + r.msg : "⚠️ " + (r.err||(r.err_list||[]).join("; ")), !r.ok);\n  refresh(); renderLib();\n}\n\nfunction renderLib() {\n  const el = document.getElementById("lib");\n  el.innerHTML = DB.map(m => `<div class="lcard">\n    <img src="${m.image||""}" onerror="this.style.display=\'none\'">\n    <div class="linfo"><b>${m.title||""}</b><div class="sub">${m.year||""} · ★${m.rating||""} · ${m.kind===\'episode\'?m.episode:\'Movie\'}</div></div>\n    <button onclick="delMovie(\'${m.id}\')">🗑</button>\n  </div>`).join("") || \'<p style="color:#888">No movies yet.</p>\';\n}\n\nasync function delMovie(id) {\n  const r = await post("/api/delete", { id });\n  msg(r.ok ? "🗑 Deleted" : "⚠️ " + r.err, !r.ok);\n  refresh(); renderLib();\n}\n\n// ---------- init ----------\nwindow.addEventListener(\'scroll\', () => document.querySelector(\'.nav\').classList.toggle(\'solid\', scrollY > 40));\nasync function init() {\n  await refresh();\n  const path = location.pathname;\n  const wm = path.match(/^\\/watch\\/([^\\/]+)/);\n  if (wm) { await openWatch(wm[1]); }\n  else { renderHome(); }\n}\ninit();\n</script>\n</body>\n</html>\n'



# ====================================================================
#                           BACKEND ROUTES
# ====================================================================
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