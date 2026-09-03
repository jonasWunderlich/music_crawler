import json
import os
import re

# --- EINSTELLUNGEN ---
LIBRARY_FILE = "lists/library.json"  # Deine bestehende Hauptdatei
ENRICH_DIR = "./log"  # Ordner mit 2026.json, 1954.json etc.
OUTPUT_FILE = "/Users/za_jonas/repos/hss/Quarkus/src/main/resources/library.json"  # Output-Datei
YEARS_OUTPUT_FILE = "/Users/za_jonas/repos/hss/Quarkus/src/main/resources/releaseYears.json"  # Output-Datei
COVER_BASE_DIR = "cover"  # Basis-Ordner für Cover-Pfade (z. B. "cover/1972/artist--album.webp")


def sanitize_filename(name) -> str:
    """
    1:1 die exakte Funktion aus dem Album Cover Downloader.
    Unterstützt Strings und Arrays (Array-Elemente werden wie in music.txt mit '; ' gefügt).
    """
    if not name:
        return ""

    if isinstance(name, list):
        name = "; ".join([str(item) for item in name if item])

    name = str(name)

    # 1. Umlaute und Sonderzeichen
    name = name.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    name = name.replace("Ä", "Ae").replace("Ö", "Oe").replace("Ü", "Ue")

    # 2. Alles außer Buchstaben und Zahlen durch Bindestrich ersetzen
    name = re.sub(r'[^a-zA-Z0-9]+', '-', name)

    # 3. Mehrfache Bindestriche reduzieren
    name = re.sub(r'-+', '-', name)

    # 4. Bindestriche am Rand entfernen, in Lowercase umwandeln & max. 200 Zeichen
    return name.strip("-").lower()[:200]


def generate_cover_url(release_year, artist, album_title):
    if not release_year or not artist or not album_title:
        return None

    artist_slug = sanitize_filename(artist)
    album_slug = sanitize_filename(album_title)

    if not artist_slug:
        artist_slug = "unknown-artist"

    if not album_slug:
        album_slug = "unknown-album"

    return f"{COVER_BASE_DIR}/{release_year}/{artist_slug}--{album_slug}.webp"


def normalize_string(val):
    if not val:
        return ""
    if isinstance(val, list):
        val = "; ".join([str(item) for item in val if item])
    return re.sub(r"[^a-z0-9]", "", str(val).lower())


def make_match_key(artist, album):
    return f"{normalize_string(artist)}___{normalize_string(album)}"


def load_crawled_year_data(folder_path):
    lookup = {}

    if not os.path.exists(folder_path):
        print(f"Hinweis: Ordner '{folder_path}' nicht gefunden. Anreicherung übersprungen.")
        return lookup

    for file_name in os.listdir(folder_path):
        if not file_name.endswith(".json"):
            continue

        file_path = os.path.join(folder_path, file_name)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

                if not isinstance(data, dict):
                    continue

                for raw_key, item in data.items():
                    if " - " in raw_key:
                        artist, album = raw_key.split(" - ", 1)
                        match_key = make_match_key(artist, album)
                        lookup[match_key] = item

        except Exception as e:
            print(f"Fehler beim Lesen von {file_name}: {e}")

    return lookup


def enrich_album(album_item, crawl_info):
    if not crawl_info:
        return

    links = crawl_info.get("links", {})
    mb_info = crawl_info.get("musicbrainz", {})

    urlWikipedia = crawl_info.get("wikipedia")
    if urlWikipedia and not album_item.get("urlWikipedia"):
        album_item["urlWikipedia"] = urlWikipedia

    urlArtist = links.get("ARTIST_LINK")
    if urlArtist and not album_item.get("urlArtist"):
        album_item["urlArtist"] = urlArtist

    urlAlbum = links.get("ALBUM_LINK")
    if urlAlbum and not album_item.get("urlAlbum"):
        album_item["urlAlbum"] = urlAlbum

    urlVideo = links.get("VIDEO_LINK")
    if urlVideo and not album_item.get("video"):
        album_item["urlVideo"] = urlVideo

    mb_release_date = mb_info.get("first-release-date")
    if mb_release_date and not album_item.get("first_release_date"):
        album_item["first_release_date"] = mb_release_date


def export_years_and_decades(albums, output_file):
    years_set = set()

    for item in albums:
        year_raw = item.get("releaseYear") or item.get("year")
        if year_raw:
            try:
                year_int = int(year_raw)
                years_set.add(year_int)
            except (ValueError, TypeError):
                continue

    sorted_years = sorted(list(years_set))
    decades_set = {(year // 10) * 10 for year in sorted_years}
    sorted_decades = sorted(list(decades_set))

    result_data = {
        "releaseYears": sorted_years,
        "decades": sorted_decades
    }

    print(f"Speichere Jahre & Jahrzehnte in '{output_file}'...")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result_data, f, indent=2, ensure_ascii=False)


def main():
    crawl_lookup = load_crawled_year_data(ENRICH_DIR)

    print(f"Lese Hauptdatei '{LIBRARY_FILE}'...")
    with open(LIBRARY_FILE, "r", encoding="utf-8") as f:
        library = json.load(f)

    is_list = isinstance(library, list)
    raw_albums = library if is_list else library.get("albums", [])

    # Filter: Nur Alben behalten, die NICHT hidden: true haben
    albums = [item for item in raw_albums if item.get("hidden") is not True]
    hidden_count = len(raw_albums) - len(albums)

    covers_generated = 0
    enriched_count = 0

    for item in albums:
        artist = item.get("albumArtist") or item.get("artist")
        album_title = item.get("title") or item.get("album")
        release_year = item.get("releaseYear") or item.get("year")

        # 1. urlCover deterministisch generieren (falls nicht vorhanden)
        if not item.get("urlCover"):
            generated_url = generate_cover_url(release_year, artist, album_title)
            if generated_url:
                item["urlCover"] = generated_url
                covers_generated += 1

        # 2. Metadaten aus den gecrawlten Jahres-JSONs anreichern
        if artist and album_title:
            match_key = make_match_key(artist, album_title)
            if match_key in crawl_lookup:
                enrich_album(item, crawl_lookup[match_key])
                enriched_count += 1

    print(f"-> {hidden_count} versteckte Alben (hidden: true) komplett entfernt.")
    print(f"-> Für {covers_generated} Alben wurde die 'urlCover' generiert.")
    print(f"-> {enriched_count} Alben wurden mit Crawl-Daten angereichert.")

    # Gefilterte Liste zurückschreiben
    output_data = albums if is_list else {"albums": albums}

    print(f"Speichere bereinigtes JSON ({len(albums)} Alben) in '{OUTPUT_FILE}'...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    # 3. releaseYears.json exportieren (nutzt bereits das gefilterte 'albums'-Array)
    export_years_and_decades(albums, YEARS_OUTPUT_FILE)

    print("Fertig!")


if __name__ == "__main__":
    main()