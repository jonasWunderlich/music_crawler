#!/usr/bin/env python3
"""
export_albums.py
----------------
Liest alle Alben aus lists/_full.txt (Primärquelle) und reichert sie
mit Daten aus den log/*.json-Dateien an. Das Ergebnis wird als kompaktes
JSON für den Datenbankimport gespeichert.

Ausgabe: export/albums.json

Felder im Output (entsprechen der Album-Entity):
  title, album_artist, artist, releaseYear, addedDate, publisher, genre, style,
  country, city, rating, reissue, fan, favorite, owned, tino, wire, hidden,
  videoUrl, wikiUrl, discogsUrl, bandcampUrl, rymUrl, mbRating
"""

import json
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Pfade
# ---------------------------------------------------------------------------
BASE_DIR    = Path(__file__).parent
FULL_TXT    = BASE_DIR / "lists" / "_full.txt"
LOG_DIR     = BASE_DIR / "log"
EXPORT_DIR  = BASE_DIR / "export"
OUT_FILE    = EXPORT_DIR / "albums.json"

# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def parse_full_txt(path: Path) -> list[dict]:
    """
    Liest _full.txt und gibt eine Liste von Album-Dicts zurück.
    Jede Zeile hat das Format:
      TAG_FOO=value TAG_BAR=value ...
    """
    albums = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue

            # Tags per Regex extrahieren: KEY=VALUE (VALUE endet beim nächsten TAG_ oder Zeilenende)
            tokens = re.findall(r"TAG_(\w+)=(.*?)(?=\s+TAG_\w+=|$)", line)
            if not tokens:
                continue

            record: dict = {}
            for key, value in tokens:
                record[key] = value.strip()

            albums.append(record)

    return albums


def load_log_index(log_dir: Path) -> dict[str, dict]:
    """
    Lädt alle log/*.json-Dateien und baut einen Index
      { "Artist - Album": { ...log_data... }, ... }
    """
    index: dict[str, dict] = {}
    for json_file in sorted(log_dir.glob("*.json")):
        try:
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"  [WARN] Konnte {json_file.name} nicht lesen: {e}", file=sys.stderr)
            continue

        for key, entry in data.items():
            # Schlüssel können doppelt vorkommen (selten) – neuerer Wert gewinnt
            index[key] = entry

    return index


def extract_url_from_relations(relations: list, rel_type: str) -> str | None:
    """Gibt die erste URL einer bestimmten MusicBrainz-Relation zurück."""
    for rel in relations:
        if rel.get("type") == rel_type:
            url = rel.get("url", {})
            return url.get("resource")
    return None


def safe_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def safe_bool(value: str | None) -> bool | None:
    """Konvertiert '0'/'1' zu False/True, None wenn leer."""
    if value is None or value == "":
        return None
    return value.strip() == "1"


def build_album(record: dict, log_index: dict[str, dict]) -> dict:
    """
    Kombiniert einen _full.txt-Eintrag mit den optionalen Log-Daten.
    Alle Künstler-abhängige Logik (Log-Lookup, Dedup-Key) verwendet ALBUM_ARTIST.
    """
    album_artist = record.get("ALBUM_ARTIST", "") or record.get("ARTIST", "")
    artist = record.get("ARTIST", "")
    album  = record.get("ALBUM",  "")
    key    = f"{album_artist} - {album}"

    log = log_index.get(key, {})
    mb  = log.get("musicbrainz", {})
    mb_relations = mb.get("relations", [])
    links = log.get("links", {})

    # --- Basis-Felder aus _full.txt ---
    rating_raw = record.get("RATING", "")
    rating = safe_int(rating_raw) if rating_raw and rating_raw.strip() else None

    # --- MusicBrainz-Daten ---
    mb_rating_raw = mb.get("rating", {})
    mb_rating = mb_rating_raw.get("value") if isinstance(mb_rating_raw, dict) else None

    # --- URLs ---
    discogs_url   = extract_url_from_relations(mb_relations, "discogs")
    rym_url       = extract_url_from_relations(mb_relations, "other databases")
    bandcamp_url  = links.get("ALBUM_LINK") or links.get("ARTIST_LINK") or None
    wiki_url      = log.get("wikipedia") or None
    video_url_raw = record.get("VIDEO", "")
    video_url     = video_url_raw if video_url_raw and video_url_raw != "?" else None

    return {
        "albumArtist": album_artist or None,
        "artist":      artist or None,
        "title":       album  or None,
        "releaseYear": safe_int(record.get("DATE")),
        "addedDate":   (record.get("ADDED") or "").split(" ")[0] or None,
        "publisher":   record.get("LABEL") or None,
        "genre":       record.get("GENRE") or None,
        "style":       record.get("STYLE") or None,
        "country":     record.get("COUNTRY") or None,
        "city":        record.get("CITY") or None,
        "rating":      rating,
        "reissue":     safe_bool(record.get("REISSUE")),
        "fan":         safe_bool(record.get("FAN")),
        "favorite":    safe_bool(record.get("FAVORITE")),
        "owned":       safe_bool(record.get("OWN")),
        "tino":        safe_bool(record.get("TINO")),
        "wire":        safe_bool(record.get("WIRE")),
        "hidden":      safe_bool(record.get("HIDDEN")),
        "videoUrl":    video_url,
        "wikiUrl":     wiki_url,
        "discogsUrl":  discogs_url,
        "bandcampUrl": bandcamp_url,
        "rymUrl":      rym_url,
        "mbRating":    mb_rating,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def deduplicate(albums: list[dict]) -> list[dict]:
    """
    Entfernt Duplikate basierend auf (album_artist, title).
    Bei mehreren Einträgen gewinnt der mit dem jüngsten addedDate.
    Einträge ohne Datum werden als älteste behandelt.
    """
    # Index: (albumArtist, title) → bestes Album bisher
    best: dict[tuple, dict] = {}

    for album in albums:
        key = (album.get("albumArtist") or "", album.get("title") or "")
        existing = best.get(key)

        if existing is None:
            best[key] = album
            continue

        # Vergleich über addedDate (YYYY-MM-DD String – lexikografisch korrekt)
        new_date  = album.get("addedDate")    or "0000-00-00"
        prev_date = existing.get("addedDate") or "0000-00-00"

        if new_date > prev_date:
            best[key] = album

    return list(best.values())


def main():
    print(f"Lese _full.txt: {FULL_TXT}")
    raw_albums = parse_full_txt(FULL_TXT)
    print(f"  → {len(raw_albums)} Einträge gefunden")

    print(f"Lade Log-Dateien aus: {LOG_DIR}")
    log_index = load_log_index(LOG_DIR)
    print(f"  → {len(log_index)} Log-Einträge indexiert")

    print("Kombiniere Daten …")
    albums_raw = [build_album(r, log_index) for r in raw_albums]

    # Deduplizierung
    albums = deduplicate(albums_raw)
    removed = len(albums_raw) - len(albums)
    print(f"  → {len(albums_raw)} Einträge → {len(albums)} nach Deduplizierung ({removed} Duplikate entfernt)")

    # Statistiken
    with_log   = sum(1 for a in albums if f"{a['albumArtist']} - {a['title']}" in log_index)
    with_wiki  = sum(1 for a in albums if a.get("wikiUrl"))
    with_mb    = sum(1 for a in albums if a.get("mbRating") is not None)
    with_disc  = sum(1 for a in albums if a.get("discogsUrl"))

    print(f"  → {with_log} Alben mit Log-Daten")
    print(f"  → {with_wiki} mit Wikipedia-Link")
    print(f"  → {with_mb} mit MusicBrainz-Rating")
    print(f"  → {with_disc} mit Discogs-Link")

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(albums, f, ensure_ascii=False, separators=(",", ":"))

    size_kb = OUT_FILE.stat().st_size / 1024
    print(f"\nFertig! {len(albums)} Alben → {OUT_FILE}  ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
