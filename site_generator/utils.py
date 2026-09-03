import json
import re
from pathlib import Path
from typing import Any, Dict

DEFAULT_CONFIG: Dict[str, Any] = {
    "library_path": "lists/library.json",
    "urlCrawler": {
        "musicbrainz": {
            "enabled": True,
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

def sanitize_filename(name: str) -> str:
    """Wandelt einen Album-/Künstlernamen in einen sicheren Dateinamen um."""
    if not name:
        return "unknown"
    # Ungültige Zeichen entfernen
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    # Leerzeichen und Unterstriche normalisieren
    name = re.sub(r'[\s_]+', "_", name.strip())
    # Auf 80 Zeichen kürzen
    return name[:80]

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
            # Shallow / 2-level merge
            for key, val in user_config.items():
                if isinstance(val, dict) and key in config and isinstance(config[key], dict):
                    config[key].update(val)
                else:
                    config[key] = val
        except Exception as e:
            print(f"Warning: Konnte {config_path} nicht lesen ({e}). Verwende Standard-Konfiguration.")
    return config
