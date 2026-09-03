import json
from pathlib import Path
from typing import Any, Dict, List, Optional

def normalize_album(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalisiert ein Album-Dictionary aus dem JSON in eine einheitliche Struktur."""
    artist_raw = str(raw.get("artist") or "").strip()
    album_artists = raw.get("albumArtist")
    if isinstance(album_artists, list):
        album_artists = [str(a).strip() for a in album_artists if a]
    else:
        album_artists = [str(album_artists).strip()] if album_artists else []

    if album_artists:
        display_artist = ", ".join(album_artists)
        sort_artist = album_artists[0]
    else:
        display_artist = artist_raw or "Unbekannt"
        sort_artist = artist_raw or "Unbekannt"

    title = str(raw.get("title") or raw.get("album") or "").strip()
    release_year_raw = str(raw.get("releaseYear") or "").strip()
    release_year = release_year_raw if release_year_raw.isdigit() else "0000"

    # Publisher / Label
    publishers = raw.get("publisher")
    if isinstance(publishers, list):
        label = ", ".join(str(p).strip() for p in publishers if p)
        publisher_list = [str(p).strip() for p in publishers if p]
    elif publishers:
        label = str(publishers).strip()
        publisher_list = [label]
    elif raw.get("label"):
        label = str(raw.get("label")).strip()
        publisher_list = [label]
    else:
        label = ""
        publisher_list = []

    # Genre & Style
    genres = raw.get("genre")
    genre = ", ".join(str(g).strip() for g in genres if g) if isinstance(genres, list) else str(genres or "").strip()

    styles = raw.get("style")
    style = ", ".join(str(s).strip() for s in styles if s) if isinstance(styles, list) else str(styles or "").strip()

    country = str(raw.get("country") or "").strip()
    city = str(raw.get("city") or "").strip()

    # Rating
    rating_raw = raw.get("rating")
    if rating_raw is not None and str(rating_raw).strip().isdigit():
        rating_int = int(str(rating_raw).strip())
        rating_str = str(rating_int)
    else:
        rating_int = 0
        rating_str = "?"

    added_date = str(raw.get("addedDate") or "0000-00-00 00:00:00").strip()
    video = str(raw.get("video") or "").strip()
    if video == "?" or video.lower() == "none" or video.lower() == "null":
        video = ""

    # Booleans
    hidden = bool(raw.get("hidden"))
    reissue = bool(raw.get("reissue"))
    fan = bool(raw.get("fan"))
    favorite = bool(raw.get("favorite"))
    owned = bool(raw.get("owned") or raw.get("own"))
    tino = bool(raw.get("tino"))
    wire = bool(raw.get("wire"))
    wishlist = bool(raw.get("wishlist"))

    # Client-side Search text
    search_parts = [display_artist, artist_raw, title, label, country, city, genre, style]
    search_text = " ".join(filter(None, search_parts)).lower()
    if reissue:
        search_text += " reissue"
    if owned:
        search_text += " owned"
    if fan or favorite:
        search_text += " favorite fan"

    log_key = f"{display_artist} - {title}"

    return {
        "artist": artist_raw,
        "albumArtist": album_artists,
        "display_artist": display_artist,
        "sort_artist": sort_artist,
        "title": title,
        "album": title,  # Rückwärtskompatibilität
        "releaseYear": release_year,
        "date": release_year,  # Alias
        "label": label,
        "publisher": publisher_list,
        "genre": genre,
        "style": style,
        "country": country,
        "city": city,
        "rating": rating_str,
        "rating_int": rating_int,
        "addedDate": added_date,
        "video": video,
        "hidden": hidden,
        "reissue": reissue,
        "fan": fan,
        "favorite": favorite,
        "owned": owned,
        "tino": tino,
        "wire": wire,
        "wishlist": wishlist,
        "discogs_artist_id": raw.get("discogs_artist_id"),
        "discogs_release_id": raw.get("discogs_release_id"),
        "search_text": search_text,
        "log_key": log_key,
        "raw": raw,
    }

def load_library(json_path: Path = Path("lists/library.json")) -> List[Dict[str, Any]]:
    """Lädt die Musikbibliothek aus einer JSON-Datei und normalisiert alle Alben."""
    if not json_path.exists():
        raise FileNotFoundError(f"Bibliotheksdatei nicht gefunden: {json_path}")

    print(f"Lade Bibliothek aus {json_path} ...")
    with open(json_path, "r", encoding="utf-8") as f:
        raw_albums = json.load(f)

    if not isinstance(raw_albums, list):
        raise ValueError(f"Ungültiges Format in {json_path}: Liste von Alben erwartet.")

    albums = [normalize_album(item) for item in raw_albums]
    print(f"{len(albums)} Alben erfolgreich geladen.")
    return albums
