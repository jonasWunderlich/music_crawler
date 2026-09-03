import json
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# Standard-Ersetzungstabelle für Umlaute, Akzente und Sonderzeichen.
# Kann über config.json ("characterReplacements") erweitert / überschrieben werden.
DEFAULT_CHAR_REPLACEMENTS: Dict[str, str] = {
    # Deutsche Umlaute & Eszett
    "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
    "Ä": "ae", "Ö": "oe", "Ü": "ue",

    # Akzente und internationale Buchstaben
    # A
    "á": "a", "à": "a", "â": "a", "ã": "a", "å": "a", "ā": "a", "ă": "a", "ą": "a",
    "Á": "a", "À": "a", "Â": "a", "Ã": "a", "Å": "a", "Ā": "a", "Ă": "a", "Ą": "a",
    # E
    "é": "e", "è": "e", "ê": "e", "ë": "e", "ē": "e", "ė": "e", "ę": "e", "ě": "e",
    "É": "e", "È": "e", "Ê": "e", "Ë": "e", "Ē": "e", "Ė": "e", "Ę": "e", "Ě": "e",
    # I
    "í": "i", "ì": "i", "î": "i", "ï": "i", "ī": "i", "į": "i", "ı": "i",
    "Í": "i", "Ì": "i", "Î": "i", "Ï": "i", "Ī": "i", "Į": "i", "İ": "i",
    # O
    "ó": "o", "ò": "o", "ô": "o", "õ": "o", "ø": "o", "ō": "o", "ő": "o",
    "Ó": "o", "Ò": "o", "Ô": "o", "Õ": "o", "Ø": "o", "Ō": "o", "Ő": "o",
    # U
    "ú": "u", "ù": "u", "û": "u", "ū": "u", "ů": "u", "ű": "u", "ų": "u",
    "Ú": "u", "Ù": "u", "Û": "u", "Ū": "u", "Ů": "u", "Ű": "u", "Ų": "u",
    # Y
    "ý": "y", "ÿ": "y", "Ý": "y", "Ÿ": "y",
    # C
    "ç": "c", "ć": "c", "č": "c", "ĉ": "c", "ċ": "c",
    "Ç": "c", "Ć": "c", "Č": "c", "Ĉ": "c", "Ċ": "c",
    # D
    "đ": "d", "ð": "d", "ď": "d",
    "Đ": "d", "Ð": "d", "Ď": "d",
    # G
    "ğ": "g", "ĝ": "g", "ġ": "g", "ģ": "g",
    "Ğ": "g", "Ĝ": "g", "Ġ": "g", "Ģ": "g",
    # L
    "ł": "l", "ĺ": "l", "ľ": "l", "ļ": "l",
    "Ł": "l", "Ĺ": "l", "Ľ": "l", "Ļ": "l",
    # N
    "ñ": "n", "ń": "n", "ň": "n", "ņ": "n",
    "Ñ": "n", "Ń": "n", "Ň": "n", "Ņ": "n",
    # R
    "ř": "r", "ŕ": "r", "ŗ": "r",
    "Ř": "r", "Ŕ": "r", "Ŗ": "r",
    # S
    "š": "s", "ś": "s", "ş": "s", "ŝ": "s",
    "Š": "s", "Ś": "s", "Ş": "s", "Ŝ": "s",
    # T
    "ť": "t", "ţ": "t", "ț": "t", "þ": "th",
    "Ť": "t", "Ţ": "t", "Ț": "t", "Þ": "th",
    # Z
    "ž": "z", "ź": "z", "ż": "z",
    "Ž": "z", "Ź": "z", "Ż": "z",
    # Ligaturen
    "æ": "ae", "Æ": "ae",
    "œ": "oe", "Œ": "oe",
}

DEFAULT_CONFIG: Dict[str, Any] = {
    "library_path": "lists/library.json",
    "characterReplacements": {},
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

def sanitize_filename(name: str, custom_replacements: Optional[Dict[str, str]] = None) -> str:
    """
    Wandelt einen Album- oder Künstlernamen in einen sicheren, einheitlichen Dateinamen um.
    - Wendet Umlaute und konfigurierbare Zeichen-Ersetzungen an
    - Ersetzt Sonderzeichen / Leerzeichen durch Bindestriche
    - Wandelt alles in Kleinbuchstaben um
    """
    if not name:
        return "unknown"

    replacements = dict(DEFAULT_CHAR_REPLACEMENTS)
    if custom_replacements:
        replacements.update(custom_replacements)

    # Zeichen ersetzen
    for src, target in replacements.items():
        if src in name:
            name = name.replace(src, target)

    # Alles außer Buchstaben und Zahlen durch Bindestrich ersetzen
    name = re.sub(r"[^a-zA-Z0-9]+", "-", name)
    # Mehrfache Bindestriche reduzieren
    name = re.sub(r"-+", "-", name)

    return name.strip("-").lower()[:200]

def legacy_sanitize_filename(name: str) -> str:
    """
    Frühere Sanitize-Funktion (nur deutsche Umlaute ersetzt, sonst alles [^a-zA-Z0-9] -> '-').
    Wird als Fallback für bestehende Cover-Dateien auf der Festplatte genutzt.
    """
    if not name:
        return "unknown"
    name = name.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    name = name.replace("Ä", "Ae").replace("Ö", "Oe").replace("Ü", "Ue")
    name = re.sub(r"[^a-zA-Z0-9]+", "-", name)
    name = re.sub(r"-+", "-", name)
    return name.strip("-").lower()[:200]

def find_cover_file(
    display_artist: str,
    raw_artist: str,
    album: str,
    release_year: str,
    thumb_dir: Path = Path("export/thumb"),
    org_dir: Path = Path("album_covers/org"),
    custom_replacements: Optional[Dict[str, str]] = None
) -> Tuple[str, bool]:
    """
    Sucht ein Cover für ein Album auf der Festplatte.
    Prüft:
      1. Modern sanitizter Name (WebP in thumb/ bzw. JPG in org/)
      2. Legacy sanitizter Name (für bestehende Dateien)
      3. Fallback mit raw_artist (falls display_artist abweicht)

    Gibt ein Tupel zurück: (relativer_html_pfad, gefunden_bool).
    """
    tag_date = str(release_year).strip() or "0000"
    artists = [display_artist]
    if raw_artist and raw_artist != display_artist:
        artists.append(raw_artist)

    for a in artists:
        # 1. Moderne Sanitize-Variante (WebP)
        m_name = f"{sanitize_filename(a, custom_replacements)}--{sanitize_filename(album, custom_replacements)}"
        m_webp = thumb_dir / tag_date / f"{m_name}.webp"
        if m_webp.exists():
            return f"thumb/{tag_date}/{m_name}.webp", True

        # 2. Legacy-Variante (WebP)
        l_name = f"{legacy_sanitize_filename(a)}--{legacy_sanitize_filename(album)}"
        l_webp = thumb_dir / tag_date / f"{l_name}.webp"
        if l_webp.exists():
            return f"thumb/{tag_date}/{l_name}.webp", True

        # 3. Falls nur Original in org/ existiert
        m_jpg = org_dir / tag_date / f"{m_name}.jpg"
        if m_jpg.exists():
            return f"../album_covers/org/{tag_date}/{m_name}.jpg", True

        l_jpg = org_dir / tag_date / f"{l_name}.jpg"
        if l_jpg.exists():
            return f"../album_covers/org/{tag_date}/{l_name}.jpg", True

    # Nicht gefunden: Standard-Erwartungspfad zurückgeben
    default_name = f"{sanitize_filename(display_artist, custom_replacements)}--{sanitize_filename(album, custom_replacements)}.webp"
    return f"thumb/{tag_date}/{default_name}", False

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
