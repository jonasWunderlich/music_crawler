#!/usr/bin/env python3
"""
Album Cover Downloader
Parst eine HTML-Datei mit Musikalben (Format: Künstler, Album, Label, Land, Genre)
und lädt passende Album-Cover in Originalgröße herunter.
Zusätzlich wird eine auf 300px Breite skalierte Version im Unterordner 'thumbs/' gespeichert.

Quellen (in dieser Reihenfolge):
  1. MusicBrainz + Cover Art Archive (kostenlos, kein API-Key nötig)
  2. Last.fm API  (LAST_FM_API_KEY als Env-Variable oder in der Konfiguration setzen)
  3. iTunes Search API (kein Key nötig, aber nur 100px → hochskaliert)

Requirements für Thumbnails: pip install Pillow
"""

import os
import re
import sys
import time
import json
import html
import logging
import argparse
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

# ── Konfiguration ────────────────────────────────────────────────────────────

LAST_FM_API_KEY = os.environ.get("LAST_FM_API_KEY", "")   # optional
OUTPUT_DIR      = Path("covers")
THUMB_SIZE      = 300           # Breite der Thumbnail-Version in Pixel
MAX_ORIGINAL_WIDTH = 1400       # Maximale Breite für das "Original"-Cover
DELAY_BETWEEN   = 1.0           # Sekunden zwischen API-Anfragen (Rate-Limit)
INPUT_FILE      = Path("music.html")
LOG_FILE        = Path("download_log.json")
USER_AGENT      = "MusicCoverDownloader/1.0 (github.com/example)"

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── Hilfsfunktionen ──────────────────────────────────────────────────────────

def http_get(url: str, headers: dict = None, timeout: int = 15) -> Optional[bytes]:
    """Einfacher HTTP-GET, gibt bytes oder None zurück."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        log.debug("HTTP %s für %s", e.code, url)
        return None
    except Exception as e:
        log.debug("Fehler bei %s: %s", url, e)
        return None


def sanitize_filename(name: str) -> str:
    """Wandelt einen Album-/Künstlernamen in einen sicheren Dateinamen um."""
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    name = name.strip(". ")
    return name[:120]   # max. Länge begrenzen


# ── Persistent Log ────────────────────────────────────────────────────────────

def load_log() -> dict:
    if LOG_FILE.exists():
        try:
            return json.loads(LOG_FILE.read_text(encoding="utf-8"))
        except:
            return {}
    return {}

def save_log(log_data: dict):
    LOG_FILE.write_text(json.dumps(log_data, indent=2, ensure_ascii=False), encoding="utf-8")


# ── HTML-Parser ──────────────────────────────────────────────────────────────

def parse_music_html(filepath: Path) -> list[dict]:
    """
    Liest die HTML-Datei und extrahiert Alben.
    Unterstützt sowohl das ursprüngliche Format als auch das Format mit Cover-Spalte.
    """
    if not filepath.exists():
        return []
    content = filepath.read_text(encoding="utf-8", errors="replace")

    tr_pattern = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
    td_pattern = re.compile(r"(<td[^>]*>.*?</td>)", re.DOTALL | re.IGNORECASE)
    tag_pattern = re.compile(r"<[^>]+>")

    albums = []
    for tr_match in tr_pattern.finditer(content):
        tr_inner = tr_match.group(1)
        # Skip header rows
        if "<th" in tr_inner.lower():
            continue
            
        tds = td_pattern.findall(tr_inner)
        if len(tds) < 3:
            continue

        def clean(text: str) -> str:
            text = tag_pattern.sub("", text)
            text = html.unescape(text)
            return " ".join(text.split())

        # Erkennung der Cover-Spalte anhand der Klasse im td-Tag
        has_cover_cell = 'class="cover-cell"' in tds[0].lower()
        
        if has_cover_cell:
            # 0: cover, 1: rating, 2: artist, 3: album, ...
            artist = clean(tds[2]) if len(tds) > 2 else ""
            album  = clean(tds[3]) if len(tds) > 3 else ""
            label  = clean(tds[4]) if len(tds) > 4 else ""
        else:
            # 0: rating, 1: artist, 2: album, ...
            artist = clean(tds[1]) if len(tds) > 1 else ""
            album  = clean(tds[2]) if len(tds) > 2 else ""
            label  = clean(tds[3]) if len(tds) > 3 else ""

        if artist and album and artist != "?" and album != "?":
            albums.append({"artist": artist, "album": album, "label": label})

    log.info("Gefundene Alben in %s: %d", filepath.name, len(albums))
    return albums


# ── Cover-Quellen ─────────────────────────────────────────────────────────────

def try_coverartarchive(artist: str, album: str) -> Optional[bytes]:
    query = urllib.parse.quote(f'artist:"{artist}" AND release:"{album}"')
    url = f"https://musicbrainz.org/ws/2/release/?query={query}&limit=3&fmt=json"
    data = http_get(url)
    if not data: return None
    time.sleep(0.5)

    try:
        releases = json.loads(data).get("releases", [])
    except: return None

    for release in releases:
        mbid = release.get("id")
        if not mbid: continue
        caa_url = f"https://coverartarchive.org/release/{mbid}"
        caa_data = http_get(caa_url)
        if not caa_data: continue
        try:
            images = json.loads(caa_data).get("images", [])
            for img in images:
                if img.get("front", False) or not images:
                    thumbs = img.get("thumbnails", {})
                    img_url = thumbs.get("1200") or thumbs.get("large") or img.get("image")
                    if img_url:
                        cover = http_get(img_url)
                        if cover and len(cover) > 5000: return cover
        except: continue
    return None

def try_lastfm(artist: str, album: str) -> Optional[bytes]:
    if not LAST_FM_API_KEY: return None
    params = urllib.parse.urlencode({"method":"album.getinfo","api_key":LAST_FM_API_KEY,"artist":artist,"album":album,"format":"json","autocorrect":"1"})
    data = http_get(f"https://ws.audioscrobbler.com/2.0/?{params}")
    if not data: return None
    try:
        images = json.loads(data).get("album", {}).get("image", [])
        for img in reversed(images):
            url = img.get("#text", "")
            if url:
                cover = http_get(url)
                if cover and len(cover) > 5000: return cover
    except: pass
    return None

def try_itunes(artist: str, album: str) -> Optional[bytes]:
    params = urllib.parse.urlencode({"term": f"{artist} {album}", "media": "music", "entity": "album", "limit": "5"})
    data = http_get(f"https://itunes.apple.com/search?{params}")
    if not data: return None
    try:
        results = json.loads(data).get("results", [])
        for res in results:
            url = res.get("artworkUrl100", "")
            if url:
                hq_url = re.sub(r"\d+x\d+bb", f"{MAX_ORIGINAL_WIDTH}x{MAX_ORIGINAL_WIDTH}bb", url)
                cover = http_get(hq_url)
                if cover and len(cover) > 5000: return cover
    except: pass
    return None


# ── Hauptlogik ────────────────────────────────────────────────────────────────

def download_cover(album_info: dict, output_dir: Path) -> tuple[bool, Optional[str], Optional[str]]:
    """Gibt (Erfolg, Quelle/Grund, Dateiname) zurück."""
    artist = album_info["artist"]
    album  = album_info["album"]
    filename = f"{sanitize_filename(artist)} - {sanitize_filename(album)}.jpg"
    filepath = output_dir / filename

    if filepath.exists():
        return True, "Bereits vorhanden", filename

    log.info("Suche Cover: %s – %s", artist, album)
    
    def try_all_apis(search_artist: str, search_album: str) -> Optional[tuple[bytes, str]]:
        # MusicBrainz
        data = try_coverartarchive(search_artist, search_album)
        if data: return data, "Cover Art Archive"
        # Last.fm
        data = try_lastfm(search_artist, search_album)
        if data: return data, "Last.fm"
        # iTunes
        data = try_itunes(search_artist, search_album)
        if data: return data, "iTunes"
        return None

    # 1. Versuch mit vollem Namen
    result = try_all_apis(artist, album)
    
    # 2. Versuch mit Fallback (nur vor dem Komma), falls nötig
    if not result and "," in artist:
        cleaned_artist = artist.split(",")[0].strip()
        log.info("  → Kein Treffer. Versuche Fallback: %s", cleaned_artist)
        result = try_all_apis(cleaned_artist, album)

    if result:
        data, source = result
        save_cover(data, filepath, output_dir, filename)
        log.info("  ✓ Gefunden via %s", source)
        return True, source, filename

    log.warning("  ✗ Kein Cover gefunden für: %s - %s", artist, album)
    return False, "Not found in any API", None

def save_cover(data: bytes, filepath: Path, output_dir: Path, filename: str):
    # Skalieren und speichern
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(data)).convert("RGB")
        if img.width > MAX_ORIGINAL_WIDTH:
            new_h = round(img.height * MAX_ORIGINAL_WIDTH / img.width)
            img = img.resize((MAX_ORIGINAL_WIDTH, new_h), Image.LANCZOS)
            img.save(filepath, "JPEG", quality=95)
        else:
            filepath.write_bytes(data)
        
        # Thumbnail
        thumb_dir = output_dir / "thumbs"
        thumb_dir.mkdir(exist_ok=True)
        new_h_thumb = round(img.height * THUMB_SIZE / img.width)
        thumb = img.resize((THUMB_SIZE, new_h_thumb), Image.LANCZOS)
        thumb.save(thumb_dir / filename, "JPEG", quality=85)
        log.info("  → Original gespeichert: %s", filename)
        log.info("  → Thumbnail (%dx%dpx) gespeichert in thumbs/", THUMB_SIZE, new_h_thumb)
    except ImportError:
        filepath.write_bytes(data)
        log.error("! Fehler beim Verarbeiten des Originals: No module named 'PIL'")
    except Exception as e:
        log.error("! Fehler beim Thumbnail: %s", e)

def update_html_with_covers(input_path: Path, output_path: Path, output_dir: Path) -> None:
    content = input_path.read_text(encoding="utf-8")
    thumb_dir = output_dir / "thumbs"
    
    tr_pattern = re.compile(r"<tr[^>]*>.*?</tr>", re.DOTALL | re.IGNORECASE)
    td_pattern = re.compile(r"(<td[^>]*>.*?</td>)", re.DOTALL | re.IGNORECASE)
    tag_pattern = re.compile(r"<[^>]+>")
    img_cleanup_pattern = re.compile(r"<img[^>]*class=['\"]cover-thumb['\"][^>]*>\s*", re.IGNORECASE)

    placeholder_style = (
        "width:50px;height:50px;background:#eee;border:1px solid #ccc;"
        "display:flex;align-items:center;justify-content:center;"
        "font-size:8px;color:#999;text-align:center;line-height:1;margin:0 auto;"
    )

    def process_tr(m: re.Match) -> str:
        tr_html = m.group(0)
        if "<th" in tr_html.lower():
            if 'class="cover-header"' not in tr_html:
                return re.sub(r"(<tr[^>]*>)\s*(<th)", r'\1<th class="cover-header" style="width:60px;">Cover</th>\2', tr_html, count=1, flags=re.IGNORECASE)
            return tr_html

        tds = td_pattern.findall(tr_html)
        if len(tds) < 3: return tr_html

        def td_text(td: str) -> str:
            return " ".join(tag_pattern.sub("", html.unescape(td)).split())

        has_cover_cell = 'class="cover-cell"' in tds[0].lower()
        if has_cover_cell:
            if len(tds) < 4: return tr_html
            artist = td_text(tds[2]); album = td_text(tds[3])
        else:
            artist = td_text(tds[1]); album = td_text(tds[2])

        thumb_name = f"{sanitize_filename(artist)} - {sanitize_filename(album)}.jpg"
        thumb_path = thumb_dir / thumb_name
        
        if thumb_path.exists():
            rel = thumb_path.relative_to(input_path.parent)
            content_html = f'<img src="{rel.as_posix()}" class="cover-thumb" style="width:50px;height:auto;display:block;margin:0 auto;">'
        else:
            content_html = f'<div class="cover-placeholder" style="{placeholder_style}">NO<br>COVER</div>'

        new_td = f'<td class="cover-cell" style="width:60px;text-align:center;vertical-align:middle;">{content_html}</td>'
        
        temp_tr = tr_html
        if has_cover_cell:
            for old_td in tds[1:]:
                clean_td = img_cleanup_pattern.sub("", old_td)
                temp_tr = temp_tr.replace(old_td, clean_td, 1)
            return temp_tr.replace(tds[0], new_td, 1)
        else:
            for old_td in tds:
                clean_td = img_cleanup_pattern.sub("", old_td)
                temp_tr = temp_tr.replace(old_td, clean_td, 1)
            return re.sub(r"(<tr[^>]*>)", rf"\1\n        {new_td}", temp_tr, count=1, flags=re.IGNORECASE)

    updated = tr_pattern.sub(process_tr, content)
    output_path.write_text(updated, encoding="utf-8")
    log.info("HTML gespeichert: %s", output_path.name)

def main():
    try:
        import questionary
    except ImportError:
        log.error("Bitte installiere questionary: pip install questionary")
        sys.exit(1)

    # 1. HTML-Dateien suchen (_*.html)
    html_files = sorted(list(Path(".").glob("_*.html")))
    if not html_files:
        log.error("Keine Dateien mit Format _*.html gefunden.")
        sys.exit(1)

    selected_file_str = questionary.select(
        "Welche HTML-Datei soll verarbeitet werden?",
        choices=[f.name for f in html_files]
    ).ask()
    
    if not selected_file_str:
        sys.exit(0)
    
    input_file = Path(selected_file_str)
    # Ziel-Datei ohne führenden Underscore
    output_file = Path(selected_file_str[1:]) if selected_file_str.startswith("_") else Path(f"processed_{selected_file_str}")

    # 2. Limit abfragen
    limit_choice = questionary.select(
        "Maximale Anzahl an Downloads?",
        choices=["10", "50", "100", "Alle"]
    ).ask()

    if not limit_choice:
        sys.exit(0)

    limit = 0 if limit_choice == "Alle" else int(limit_choice)

    # 3. Download-Optionen
    retry_choice = questionary.confirm("Fehlgeschlagene Alben erneut versuchen?", default=False).ask()

    # Logik ausführen
    log_data = load_log()
    output_path = OUTPUT_DIR
    output_path.mkdir(parents=True, exist_ok=True)
    
    albums = parse_music_html(input_file)
    processed_count = 0
    success = 0; failed = 0
    
    for i, album_info in enumerate(albums, 1):
        if limit > 0 and processed_count >= limit:
            log.info("Limit von %d Verarbeitungen erreicht. Breche ab.", limit)
            break
            
        key = f"{album_info['artist']} - {album_info['album']}"
        
        # Überspringe, wenn bereits erfolgreich (außer wir wollen explizit alles neu machen, was hier nicht der Fall ist)
        if log_data.get(key, {}).get("status") == "success":
            continue
            
        # Überspringe fehlgeschlagene, wenn retry_choice False ist
        if not retry_choice and log_data.get(key, {}).get("status") == "failed":
            continue
        
        # Jetzt zählen wir dieses Album als verarbeitet
        processed_count += 1
        log.info("[%d] Verarbeite: %s", processed_count, key)
        
        ok, source, _ = download_cover(album_info, output_path)
        
        log_data[key] = {
            "status": "success" if ok else "failed",
            "timestamp": time.ctime()
        }
        if ok:
            log_data[key]["source"] = source
            success += 1
        else:
            log_data[key]["reason"] = source
            failed += 1
        save_log(log_data)

    log.info("─" * 50)
    log.info("Fertig!  Echte Verarbeitungen: %d | Erfolgreich: %d | Fehlgeschlagen: %d", processed_count, success, failed)
    
    # HTML mit Cover-Vorschauen aktualisieren (Original -> Neu)
    log.info("Erstelle neue HTML-Datei: %s ...", output_file.name)
    update_html_with_covers(input_file, output_file, output_path)

if __name__ == "__main__":
    main()
