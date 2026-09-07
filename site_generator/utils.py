import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

REPLACEMENTS_FILE = Path("replacements.json")

# Fallback-Tabelle falls replacements.json nicht vorhanden ist
DEFAULT_CHAR_REPLACEMENTS: Dict[str, str] = {
    # Symbole
    "&": "and",
    "+": "plus",
    "@": "at",
    "%": "percent",
    "$": "s",
    "€": "eur",
    "=": "equals",
    "#": "number",

    # Deutsche Umlaute & Eszett
    "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
    "Ä": "ae", "Ö": "oe", "Ü": "ue",

    # Ligaturen & Spezialbuchstaben
    "æ": "ae", "Æ": "ae",
    "œ": "oe", "Œ": "oe",
    "ø": "oe", "Ø": "oe",
    "ð": "d", "Ð": "d",
    "þ": "th", "Þ": "th",
    "ł": "l", "Ł": "l",
    "đ": "d", "Đ": "d",

    # Kyrillisch
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu",
    "я": "ya",
    "А": "a", "Б": "b", "В": "v", "Г": "g", "Д": "d", "Е": "e", "Ё": "yo", "Ж": "zh",
    "З": "z", "И": "i", "Й": "y", "К": "k", "Л": "l", "М": "m", "Н": "n", "О": "o",
    "П": "p", "Р": "r", "С": "s", "Т": "t", "У": "u", "Ф": "f", "Х": "kh", "Ц": "ts",
    "Ч": "ch", "Ш": "sh", "Щ": "shch", "Ъ": "", "Ы": "y", "Ь": "", "Э": "e", "Ю": "yu",
    "Я": "ya",
    "і": "i", "І": "i", "ї": "yi", "Ї": "yi", "є": "ye", "Є": "ye",

    # Griechisch
    "α": "a", "β": "v", "γ": "g", "δ": "d", "ε": "e", "ζ": "z", "η": "i", "θ": "th",
    "ι": "i", "κ": "k", "λ": "l", "μ": "m", "ν": "n", "ξ": "x", "ο": "o", "π": "p",
    "ρ": "r", "σ": "s", "ς": "s", "τ": "t", "υ": "y", "φ": "f", "χ": "ch", "ψ": "ps",
    "ω": "o",
    "Α": "a", "Β": "v", "Γ": "g", "Δ": "d", "Ε": "e", "Ζ": "z", "Η": "i", "Θ": "th",
    "Ι": "i", "Κ": "k", "Λ": "l", "Μ": "m", "Ν": "n", "Ξ": "x", "Ο": "o", "Π": "p",
    "Ρ": "r", "Σ": "s", "Τ": "t", "Υ": "y", "Φ": "f", "Χ": "ch", "Ψ": "ps", "Ω": "o"
}

_REPLACEMENTS_CACHE: Optional[Dict[str, Any]] = None

def load_replacements(path: Path = REPLACEMENTS_FILE) -> Dict[str, Any]:
    """Lädt die Ersetzungstabellen aus replacements.json mit In-Memory-Caching."""
    global _REPLACEMENTS_CACHE
    if _REPLACEMENTS_CACHE is not None:
        return _REPLACEMENTS_CACHE

    data: Dict[str, Any] = {
        "artists": {},
        "albums": {},
        "characters": dict(DEFAULT_CHAR_REPLACEMENTS)
    }

    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                data["artists"].update(loaded.get("artists", {}))
                data["albums"].update(loaded.get("albums", {}))
                data["characters"].update(loaded.get("characters", {}))
        except Exception as e:
            print(f"Warning: Konnte {path} nicht laden ({e}). Verwende Standard-Ersetzungen.")

    _REPLACEMENTS_CACHE = data
    return _REPLACEMENTS_CACHE

def sanitize_name(
    text: Any,
    is_artist: bool = False,
    is_album: bool = False,
    max_length: int = 80,
    space_replacement: str = "_",
    replacements_data: Optional[Dict[str, Any]] = None
) -> str:
    """
    Bereinigt einen Künstler- oder Albumnamen nach der neuen Benennungslogik:
    1. Prüfung exakter Band-/Albumnamen in der Ersetzungstabelle
    2. Ersetzung von Sonderzeichen/Symbolen/Umlauten/Alphabeten
    3. Unicode-NFKD-Zerlegung für verbleibende Akzente
    4. Ersetzung von Leerzeichen durch space_replacement (Standard: '_')
    5. Kürzung auf max_length
    6. Kleinbuchstaben
    """
    if not text:
        return "unknown"

    if isinstance(text, (list, tuple)):
        text = ", ".join(str(item).strip() for item in text if item)

    rep = replacements_data or load_replacements()
    artist_map = rep.get("artists", {})
    album_map = rep.get("albums", {})
    char_map = rep.get("characters", {})

    t = str(text).strip()

    # 1. Spezifische Künstlernamen / Albumnamen
    if is_artist:
        for k, v in artist_map.items():
            if k.strip().lower() == t.lower():
                return v[:max_length].strip(f"-{space_replacement}")

    if is_album:
        for k, v in album_map.items():
            if k.strip().lower() == t.lower():
                return v[:max_length].strip(f"-{space_replacement}")

    # 2. Zeichenersetzungen aus Tabelle
    for src, dst in char_map.items():
        if src in t:
            t = t.replace(src, dst)

    # 3. Unicode NFKD-Zerlegung für verbleibende diakritische Zeichen (Akzente etc.)
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))

    # 4. Leerzeichen und unzulässige Zeichen durch space_replacement bzw. Bindestrich
    # Erlaube a-z, A-Z, 0-9 sowie Bindestriche und Unterstriche
    t = re.sub(r"[^a-zA-Z0-9_\-]+", space_replacement, t)

    # Mehrfache Unterstriche und Bindestriche normalisieren
    sep = re.escape(space_replacement)
    t = re.sub(rf"{sep}+", space_replacement, t)
    t = re.sub(r"-+", "-", t)

    # Ränder säubern und in Kleinbuchstaben
    t = t.strip(f"-{space_replacement}").lower()

    # 5. Auf Maximallänge kürzen
    if len(t) > max_length:
        t = t[:max_length].rstrip(f"-{space_replacement}")

    return t or "unknown"

def sanitize_filename(
    name: Any,
    custom_replacements: Optional[Dict[str, str]] = None,
    is_artist: bool = False,
    is_album: bool = False,
    max_length: int = 80,
    space_replacement: str = "_"
) -> str:
    """
    Allgemeine Sanitize-Funktion, kompatibel mit alten Aufrufen.
    """
    rep = load_replacements()
    if custom_replacements:
        rep_merged = {
            "artists": dict(rep.get("artists", {})),
            "albums": dict(rep.get("albums", {})),
            "characters": dict(rep.get("characters", {}))
        }
        rep_merged["characters"].update(custom_replacements)
        rep = rep_merged

    return sanitize_name(
        name,
        is_artist=is_artist,
        is_album=is_album,
        max_length=max_length,
        space_replacement=space_replacement,
        replacements_data=rep
    )

def legacy_sanitize_filename(name: Any) -> str:
    """
    Frühere Sanitize-Funktion (nur deutsche Umlaute ersetzt, sonst alles [^a-zA-Z0-9] -> '-').
    Wird als Fallback für bestehende Cover-Dateien auf der Festplatte genutzt.
    """
    if not name:
        return "unknown"
    if isinstance(name, (list, tuple)):
        name = "; ".join(str(item).strip() for item in name if item)
    name = str(name)
    name = name.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    name = name.replace("Ä", "Ae").replace("Ö", "Oe").replace("Ü", "Ue")
    name = re.sub(r"[^a-zA-Z0-9]+", "-", name)
    name = re.sub(r"-+", "-", name)
    return name.strip("-").lower()[:200]

def get_cover_stem(
    artist: Any,
    album: Any,
    naming_config: Optional[Dict[str, Any]] = None,
    custom_replacements: Optional[Dict[str, str]] = None,
    replacements_data: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Erzeugt den kanonischen Cover-Dateinamen-Stamm (ohne Endung) im Format:
    '{artist_slug}--{album_slug}'
    unter Berücksichtigung von replacements.json und Konfiguration.
    """
    n_cfg = naming_config or {}
    max_artist = n_cfg.get("max_artist_length", 80)
    max_album = n_cfg.get("max_album_length", 80)
    space_char = n_cfg.get("space_replacement", "_")

    rep = replacements_data or load_replacements()
    if custom_replacements:
        rep_merged = {
            "artists": dict(rep.get("artists", {})),
            "albums": dict(rep.get("albums", {})),
            "characters": dict(rep.get("characters", {})),
        }
        rep_merged["characters"].update(custom_replacements)
        rep = rep_merged

    artist_slug = sanitize_name(
        artist,
        is_artist=True,
        max_length=max_artist,
        space_replacement=space_char,
        replacements_data=rep,
    )
    album_slug = sanitize_name(
        album,
        is_album=True,
        max_length=max_album,
        space_replacement=space_char,
        replacements_data=rep,
    )
    return f"{artist_slug}--{album_slug}"

def get_cover_filename(
    artist: Any,
    album: Any,
    extension: str = "webp",
    naming_config: Optional[Dict[str, Any]] = None,
    custom_replacements: Optional[Dict[str, str]] = None,
    replacements_data: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Erzeugt den vollständigen Cover-Dateinamen mit Dateiendung (z.B. 'artist--album.webp').
    """
    stem = get_cover_stem(
        artist=artist,
        album=album,
        naming_config=naming_config,
        custom_replacements=custom_replacements,
        replacements_data=replacements_data,
    )
    ext = extension.lstrip(".")
    return f"{stem}.{ext}" if ext else stem

def generate_cover_url(
    release_year: Any,
    artist: Any,
    album_title: Any,
    base_dir: str = "cover",
    extension: str = "webp",
    naming_config: Optional[Dict[str, Any]] = None,
    custom_replacements: Optional[Dict[str, str]] = None,
    replacements_data: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Generiert den relativen Cover-Pfad / URL für eine Veröffentlichung
    (z.B. 'cover/1972/artist--album.webp').
    Gibt None zurück, falls release_year, artist oder album_title leer sind.
    """
    if not release_year or not artist or not album_title:
        return None

    clean_year = str(release_year).strip()
    if not clean_year or clean_year == "None":
        clean_year = "0000"

    filename = get_cover_filename(
        artist=artist,
        album=album_title,
        extension=extension,
        naming_config=naming_config,
        custom_replacements=custom_replacements,
        replacements_data=replacements_data,
    )

    clean_base = base_dir.strip("/")
    if clean_base:
        return f"{clean_base}/{clean_year}/{filename}"
    return f"{clean_year}/{filename}"

def find_cover_file(
    display_artist: str,
    raw_artist: str,
    album: str,
    release_year: str,
    thumb_dir: Path = Path("export/thumb"),
    org_dir: Path = Path("album_covers/org"),
    naming_config: Optional[Dict[str, Any]] = None,
    custom_replacements: Optional[Dict[str, str]] = None
) -> Tuple[str, bool]:
    """
    Sucht ein Cover für ein Album auf der Festplatte.
    Prüft in dieser Reihenfolge:
      1. Moderne Benennung (WebP in thumb/ mit Unterstrichen)
      2. Moderne Benennung mit raw_artist
      3. Historische Benennung (WebP mit Bindestrichen)
      4. Historische Benennung mit raw_artist
      5. Originale in album_covers/org/ (JPG)
    Gibt (relativer_html_pfad, gefunden_bool) zurück.
    """
    tag_date = str(release_year).strip() or "0000"
    n_cfg = naming_config or {}

    rep = load_replacements()
    if custom_replacements:
        rep_merged = {
            "artists": dict(rep.get("artists", {})),
            "albums": dict(rep.get("albums", {})),
            "characters": dict(rep.get("characters", {}))
        }
        rep_merged["characters"].update(custom_replacements)
        rep = rep_merged

    artists = [display_artist]
    if raw_artist and raw_artist != display_artist:
        artists.append(raw_artist)

    # 1. Moderne Namen prüfen
    for a in artists:
        modern_stem = get_cover_stem(
            a,
            album,
            naming_config=n_cfg,
            replacements_data=rep
        )

        m_webp = thumb_dir / tag_date / f"{modern_stem}.webp"
        if m_webp.exists():
            return f"thumb/{tag_date}/{modern_stem}.webp", True

        m_jpg = org_dir / tag_date / f"{modern_stem}.jpg"
        if m_jpg.exists():
            return f"../album_covers/org/{tag_date}/{modern_stem}.jpg", True

    # 2. Historische Namen (Fallback auf alte Bindestrich-Dateien)
    for a in artists:
        l_stem = f"{legacy_sanitize_filename(a)}--{legacy_sanitize_filename(album)}"

        l_webp = thumb_dir / tag_date / f"{l_stem}.webp"
        if l_webp.exists():
            return f"thumb/{tag_date}/{l_stem}.webp", True

        l_jpg = org_dir / tag_date / f"{l_stem}.jpg"
        if l_jpg.exists():
            return f"../album_covers/org/{tag_date}/{l_stem}.jpg", True

    # Standard-Pfad für den Fall, dass kein Cover existiert
    def_stem = get_cover_stem(
        display_artist,
        album,
        naming_config=n_cfg,
        replacements_data=rep
    )
    return f"thumb/{tag_date}/{def_stem}.webp", False

def get_log_path(tag_date: str, log_dir: Path = Path("log")) -> Path:
    """Gibt den Pfad zur Log-Datei für das gegebene Jahr zurück."""
    clean_date = str(tag_date).strip()
    if not clean_date or clean_date == "None":
        clean_date = "0000"
    return log_dir / f"{clean_date}.json"

def load_data_log(tag_date: str, log_dir: Path = Path("log")) -> dict:
    """Lädt die Log-Daten für ein bestimmtes Jahr."""
    log_file = get_log_path(tag_date, log_dir)
    if log_file.exists():
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {log_file}: {e}")
            return {}
    return {}

def save_data_log(tag_date: str, log_data: dict, log_dir: Path = Path("log")) -> None:
    """Speichert die Log-Daten für ein bestimmtes Jahr."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = get_log_path(tag_date, log_dir)
    try:
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving {log_file}: {e}")

DEFAULT_CONFIG: Dict[str, Any] = {
    "library_path": "lists/library.json",
    "characterReplacements": {},
    "naming": {
        "replacements_file": "replacements.json",
        "space_replacement": "_",
        "max_artist_length": 80,
        "max_album_length": 80
    },
    "urlCrawler": {
        "musicbrainz": {
            "enabled": False,
            "missing_only": False,
            "full": False
        },
        "bandcamp": {
            "enabled": True,
            "missing_only": False
        }
    },
    "pages": {
        "currentYear": {
            "enabled": True,
            "include_hidden": False,
            "sort": "addedDate",
            "sort_direction": "desc"
        },
        "years": {
            "enabled": True,
            "include_hidden": False,
            "sort": "rating",
            "sort_direction": "desc"
        },
        "decades": {
            "enabled": True,
            "include_hidden": False,
            "minimum_rating": 7,
            "sort": "rating",
            "sort_direction": "desc"
        },
        "owned": {
            "enabled": True,
            "title": "Meine Platten",
            "filename": "meine-platten.html",
            "include_hidden": False,
            "sort": "releaseYear",
            "sort_direction": "desc"
        },
        "wishlist": {
            "enabled": True,
            "title": "Meine Wishlist",
            "filename": "meine-wishlist.html",
            "include_hidden": False,
            "sort": "releaseYear",
            "sort_direction": "desc"
        },
        "favorites": {
            "enabled": True,
            "title": "Meine Favoriten",
            "filename": "meine-favoriten.html",
            "include_hidden": False,
            "sort": "releaseYear",
            "sort_direction": "desc"
        },
        "samplers": {
            "enabled": True,
            "title": "Meine Sampler",
            "filename": "meine-sampler.html",
            "label": "Wunderliche Tapes",
            "include_hidden": True,
            "sort": "releaseYear",
            "sort_direction": "desc"
        }
    },
    "ratingHoverMesseges": {
        "1": "It hurts",
        "2": "There is more music in my farts",
        "3": "I feel sleepy",
        "4": "okay",
        "5": "good",
        "6": "great",
        "7": "Very good",
        "8": "Pretty Awesome",
        "9": "Insanely Awesome",
        "10": "I fell the universe bending"
    }
}

def load_config(config_path: Path = Path("config.json")) -> dict:
    """Lädt die Konfigurationsdatei mit Fallbacks auf DEFAULT_CONFIG."""
    config = dict(DEFAULT_CONFIG)
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                user_config = json.load(f)
            for key, val in user_config.items():
                if isinstance(val, dict) and key in config and isinstance(config[key], dict):
                    config[key].update(val)
                else:
                    config[key] = val
        except Exception as e:
            print(f"Warning: Konnte {config_path} nicht lesen ({e}). Verwende Standard-Konfiguration.")
    return config
