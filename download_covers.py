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
from typing import Optional, List, Dict, Tuple
import shutil

# Fuzzy search
try:
    from thefuzz import fuzz, process
except ImportError:
    fuzz = None
    process = None

# ── Konfiguration ────────────────────────────────────────────────────────────

LAST_FM_API_KEY = os.environ.get("LAST_FM_API_KEY", "")   # optional
OUTPUT_DIR       = Path("covers")
ORIGINAL_DIR     = Path("album_covers/legacy")
LOCAL_SEARCH_DIR = Path("album_covers/local")
THUMB_SIZE       = 400           # Breite der Thumbnail-Version in Pixel
MAX_ORIGINAL_WIDTH = 1400       # Maximale Breite für das "Original"-Cover
DELAY_BETWEEN   = 1.0           # Sekunden zwischen API-Anfragen (Rate-Limit)
INPUT_FILE      = Path("music.html")
LOG_DIR            = Path("log")
USER_AGENT      = "MusicCoverDownloader/1.0 (github.com/example)"

# New Structure
ALBUM_COVERS_ORG   = Path("album_covers/org")
ALBUM_COVERS_THUMB = Path("export/thumb")
LISTS_DIR          = Path("lists")
EXPORT_DIR         = Path("export")
LOG_DIR            = Path("log")
FUZZY_THRESHOLD    = 90  # Tolerance for fuzzy search (0-100)
LEGACY_LOG_FILE    = Path("log/legacy/download_status.json")

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
    """Wandelt einen Namen in einen URL-sicheren Dateinamen um."""
    # Umlaute und Sonderzeichen
    name = name.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    name = name.replace("Ä", "Ae").replace("Ö", "Oe").replace("Ü", "Ue")
    
    # Alles außer Buchstaben und Zahlen durch Bindestrich ersetzen
    name = re.sub(r'[^a-zA-Z0-9]+', '-', name)
    
    # Mehrfache Bindestriche reduzieren
    name = re.sub(r'-+', '-', name)
    
    return name.strip("-").lower()[:200]


# ── Persistent Log ────────────────────────────────────────────────────────────

def get_log_path(tag_date: str, log_type: str = "download") -> Path:
    """Gibt den Pfad zur Logdatei für ein bestimmtes Jahr zurück."""
    year_dir = LOG_DIR / tag_date
    year_dir.mkdir(parents=True, exist_ok=True)
    if log_type == "download":
        return year_dir / "download_status.json"
    elif log_type == "links":
        return year_dir / "links.json"
    return year_dir / f"{log_type}.json"

def load_log(tag_date: str) -> dict:
    log_file = get_log_path(tag_date, "download")
    if log_file.exists():
        try:
            return json.loads(log_file.read_text(encoding="utf-8"))
        except:
            return {}
    return {}

def save_log(tag_date: str, data: dict):
    log_file = get_log_path(tag_date, "download")
    log_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


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


def parse_tags(text: str) -> Dict[str, str]:
    """Extracts all TAG_KEY=VALUE pairs from a text block."""
    matches = list(re.finditer(r'TAG_(\w+)=', text))
    data = {}
    for i in range(len(matches)):
        tag_name = matches[i].group(1)
        start_pos = matches[i].end()
        if i + 1 < len(matches):
            end_pos = matches[i+1].start()
        else:
            end_pos = len(text)
        value = text[start_pos:end_pos].strip()
        # Clean up possible trailing artifacts or newlines
        value = " ".join(value.split())
        data[tag_name] = value
    return data


def parse_music_txt(filepath: Path) -> List[Dict[str, str]]:
    """
    Liest eine .txt Datei im TAG-Format und extrahiert Alben.
    """
    if not filepath.exists():
        return []
    content = filepath.read_text(encoding="utf-8", errors="replace")
    
    # Identify records section (after *** Liste)
    list_start = content.find("*** Liste")
    if list_start != -1:
        records_raw = content[list_start:]
    else:
        records_raw = content

    record_blocks = re.split(r'(?=TAG_HIDDEN=)', records_raw)
    albums = []
    
    for block in record_blocks:
        block = block.strip()
        if not block: continue
        
        tags = parse_tags(block)
        artist = tags.get('ARTIST')
        album = tags.get('ALBUM')
        if artist and album:
            albums.append({
                "artist": artist,
                "album": album,
                "label": tags.get('LABEL', ''),
                "date": tags.get('DATE', '0000')
            })

    log.info("Gefundene Alben in %s: %d", filepath.name, len(albums))
    return albums


# ── Cover-Quellen ─────────────────────────────────────────────────────────────

def try_bandcamp(artist: str, album: str, tag_date: str) -> Optional[bytes]:
    log_file = get_log_path(tag_date, "links")
    if not log_file.exists():
        return None
        
    try:
        links = json.loads(log_file.read_text(encoding="utf-8"))
    except Exception as e:
        log.debug("Fehler beim Laden von links.json: %s", e)
        return None
        
    key = f"{artist} - {album}"
    album_link = links.get(key, {}).get("ALBUM_LINK", "")
    if not album_link or not album_link.startswith("http"):
        return None
        
    try:
        html_data = http_get(album_link)
        if not html_data: return None
        html_str = html_data.decode("utf-8", errors="ignore")
        
        # Try popupImage first (usually points to _10.jpg) or og:image
        img_match = re.search(r'<a class="popupImage" href="([^"]+)"', html_str)
        if not img_match:
            img_match = re.search(r'<meta property="og:image" content="([^"]+)"', html_str)
            
        if img_match:
            img_url = img_match.group(1)
            # Force _10.jpg for max resolution 1200x1200px
            img_url = re.sub(r'_\d+\.jpg$', '_10.jpg', img_url)
            
            cover = http_get(img_url)
            if cover and len(cover) > 5000:
                return cover
    except Exception as e:
        log.debug("Fehler bei Bandcamp Link Fetch: %s", e)
    return None

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

def fuzzy_local_search(artist: str, album: str, search_dirs: List[Path], threshold: int) -> Optional[Path]:
    """Sucht fuzzy nach einer Bilddatei in den angegebenen Ordnern."""
    if not fuzz:
        log.warning("thefuzz ist nicht installiert. Fuzzy search deaktiviert.")
        return None

    target_name = f"{sanitize_filename(artist)}--{sanitize_filename(album)}"
    best_match = None
    best_score = 0
    
    # Unterstützte Bildformate
    extensions = [".jpg", ".jpeg", ".png", ".webp"]
    
    for sdir in search_dirs:
        if not sdir.exists():
            continue
            
        files = list(sdir.glob("*"))
        for f in files:
            if f.suffix.lower() not in extensions:
                continue
                
            # Sowohl Query als auch Dateiname normalisieren für den Vergleich
            clean_stem = sanitize_filename(f.stem)
            score = fuzz.ratio(target_name, clean_stem)
            if score > best_score:
                best_score = score
                best_match = f
                
    if best_score >= threshold:
        log.info("  ✓ Fuzzy Treffer (%d%%): %s", best_score, best_match.name)
        return best_match
    
    return None

def download_cover(album_info: dict, output_dir: Path) -> tuple[bool, Optional[str], Optional[str]]:
    """Gibt (Erfolg, Quelle/Grund, Dateiname) zurück."""
    artist = album_info["artist"]
    album  = album_info["album"]
    tag_date = album_info.get("date", "0000")
    
    filename = f"{sanitize_filename(artist)}--{sanitize_filename(album)}.jpg"
    
    # Neuer Zielpfad
    dest_dir = ALBUM_COVERS_ORG / tag_date
    dest_path = dest_dir / filename
    
    # 0. Check ob bereits am Zielort vorhanden (Original UND Thumbnail)
    thumb_path = ALBUM_COVERS_THUMB / tag_date / (Path(filename).stem + ".webp")
    if dest_path.exists() and thumb_path.exists():
        return True, "Bereits vorhanden", filename
    
    # 0b. Falls Original existiert aber Thumb fehlt: Thumb generieren
    if dest_path.exists() and not thumb_path.exists():
        log.info("  → Original vorhanden, generiere fehlendes Thumbnail...")
        data = dest_path.read_bytes()
        save_cover_to_new_structure(data, filename, tag_date)
        return True, "Thumbnail nachgeneriert", filename

    log.info("Suche Cover: %s – %s (%s)", artist, album, tag_date)
    
    # 1. Fuzzy Local Search (zuerst local, dann original)
    found_local = fuzzy_local_search(artist, album, [LOCAL_SEARCH_DIR, ORIGINAL_DIR], FUZZY_THRESHOLD)
    if found_local:
        data = found_local.read_bytes()
        save_cover_to_new_structure(data, filename, tag_date)
        return True, f"Local ({found_local.parent.name})", filename

    # 2. API Suche (Bestands-Logik)
    def try_all_apis(search_artist: str, search_album: str) -> Optional[tuple[bytes, str]]:
        # Bandcamp (Best Quality)
        data = try_bandcamp(search_artist, search_album, tag_date)
        if data: return data, "Bandcamp"
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

    result = try_all_apis(artist, album)
    
    # Fallback (nur vor dem Komma)
    if not result and "," in artist:
        cleaned_artist = artist.split(",")[0].strip()
        log.info("  → Kein Treffer. Versuche Fallback: %s", cleaned_artist)
        result = try_all_apis(cleaned_artist, album)

    if result:
        data, source = result
        save_cover_to_new_structure(data, filename, tag_date)
        log.info("  ✓ Gefunden via %s", source)
        return True, source, filename

    log.warning("  ✗ Kein Cover gefunden für: %s - %s", artist, album)
    return False, "Not found", None

def save_cover_to_new_structure(data: bytes, filename: str, tag_date: str):
    """Speichert das Cover und Thumbnail in der neuen Struktur."""
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(data)).convert("RGB")
        
        # Original speichern
        dest_dir = ALBUM_COVERS_ORG / tag_date
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / filename
        
        if img.width > MAX_ORIGINAL_WIDTH:
            new_h = round(img.height * MAX_ORIGINAL_WIDTH / img.width)
            img_resized = img.resize((MAX_ORIGINAL_WIDTH, new_h), Image.LANCZOS)
            img_resized.save(dest_path, "JPEG", quality=95)
        else:
            dest_path.write_bytes(data)
        
        # Thumbnail speichern (WebP)
        thumb_dir = ALBUM_COVERS_THUMB / tag_date
        thumb_dir.mkdir(parents=True, exist_ok=True)
        new_h_thumb = round(img.height * THUMB_SIZE / img.width)
        thumb = img.resize((THUMB_SIZE, new_h_thumb), Image.LANCZOS)
        thumb_filename = Path(filename).stem + ".webp"
        thumb.save(thumb_dir / thumb_filename, "WEBP", quality=85)
        
        log.info("  → Gespeichert in: %s", dest_path)
    except Exception as e:
        log.error("! Fehler beim Speichern: %s", e)

def save_cover(data: bytes, filepath: Path, output_dir: Path, filename: str):
    # Skalieren und speichern
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(data)).convert("RGB")
        
        # Original in covers/original/
        orig_dir = ORIGINAL_DIR
        orig_dir.mkdir(parents=True, exist_ok=True)
        orig_filepath = orig_dir / filename
        if img.width > MAX_ORIGINAL_WIDTH:
            new_h = round(img.height * MAX_ORIGINAL_WIDTH / img.width)
            img = img.resize((MAX_ORIGINAL_WIDTH, new_h), Image.LANCZOS)
            img.save(orig_filepath, "JPEG", quality=95)
        else:
            orig_filepath.write_bytes(data)
        
        # Thumbnail in covers/thumbs/ (WebP)
        thumb_dir = output_dir / "thumbs"
        thumb_dir.mkdir(exist_ok=True)
        new_h_thumb = round(img.height * THUMB_SIZE / img.width)
        thumb = img.resize((THUMB_SIZE, new_h_thumb), Image.LANCZOS)
        thumb_filename = Path(filename).stem + ".webp"
        thumb.save(thumb_dir / thumb_filename, "WEBP", quality=85)
        log.info("  → Original gespeichert in org/: %s", filename)
        log.info("  → Thumbnail (%dx%dpx) als WebP gespeichert in thumbs/", THUMB_SIZE, new_h_thumb)
    except ImportError:
        ORIGINAL_DIR.mkdir(parents=True, exist_ok=True)
        (ORIGINAL_DIR / filename).write_bytes(data)
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

    # 1. Dateien suchen (*.txt) in lists/
    LISTS_DIR.mkdir(exist_ok=True)
    source_files = sorted(
        list(LISTS_DIR.glob("*.txt"))
    )
    if not source_files:
        log.error("Keine Dateien mit Format *.txt gefunden (auch nicht in %s).", LISTS_DIR)
        sys.exit(1)

    file_map = {f.stem: f for f in source_files}
    choices = sorted(list(file_map.keys()), reverse=True)

    selected_name = questionary.autocomplete(
        "Welche Datei soll verarbeitet werden? (Suche durch Tippen)",
        choices=choices
    ).ask()

    if not selected_name:
        sys.exit(0)

    input_file = file_map[selected_name]
    is_txt = input_file.suffix.lower() == ".txt"
    
    # Ziel-Datei im Export-Verzeichnis
    EXPORT_DIR.mkdir(exist_ok=True)
    output_file_name = f"{input_file.stem}.html"
    output_file = EXPORT_DIR / output_file_name

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
    if is_txt:
        albums = parse_music_txt(input_file)
    else:
        albums = parse_music_html(input_file)
        
    processed_count = 0
    success = 0; failed = 0
    log_cache = {}  # Cache für geladene Logs pro Jahr
    
    # Legacy Log laden
    legacy_log = {}
    legacy_dirty = False
    if LEGACY_LOG_FILE.exists():
        try:
            legacy_log = json.loads(LEGACY_LOG_FILE.read_text(encoding="utf-8"))
        except:
            pass
    
    for i, album_info in enumerate(albums, 1):
        if limit > 0 and processed_count >= limit:
            log.info("Limit von %d Verarbeitungen erreicht. Breche ab.", limit)
            break
            
        artist = album_info["artist"]
        album  = album_info["album"]
        tag_date = album_info.get("date", "0000")
        key = f"{artist} - {album}"

        # Log für das Jahr laden
        if tag_date not in log_cache:
            log_cache[tag_date] = load_log(tag_date)
        log_data = log_cache[tag_date]
        
        # Überspringe fehlgeschlagene, wenn retry_choice False ist
        if not retry_choice and log_data.get(key, {}).get("status") == "failed":
            continue
        
        # Jetzt zählen wir dieses Album als verarbeitet
        processed_count += 1
        log.info("[%d] Verarbeite: %s (%s)", processed_count, key, tag_date)
        
        ok, source, _ = download_cover(album_info, ALBUM_COVERS_ORG)
        
        # Falls im Legacy-Log, übernehmen wir evtl. Infos oder löschen ihn einfach (da er nun im neuen Log ist)
        if key in legacy_log:
            del legacy_log[key]
            legacy_dirty = True

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
        
        save_log(tag_date, log_data)
    
    if legacy_dirty:
        LEGACY_LOG_FILE.write_text(json.dumps(legacy_log, indent=2, ensure_ascii=False), encoding="utf-8")

    log.info("─" * 50)
    log.info("Fertig!  Echte Verarbeitungen: %d | Erfolgreich: %d | Fehlgeschlagen: %d", processed_count, success, failed)
    
    # HTML mit Cover-Vorschauen aktualisieren (Original -> Neu)
    log.info("Erstelle neue HTML-Datei: %s ...", output_file.name)
    # Beachte: update_html_with_covers nutzt noch die alte Logik. 
    # Falls das HTML aktualisiert werden soll, müssten wir hier Pfade anpassen.
    # Aber die Priorität liegt auf dem Download/Fuzzy Search.
    # update_html_with_covers(input_file, output_file, ALBUM_COVERS_ORG)

if __name__ == "__main__":
    main()
