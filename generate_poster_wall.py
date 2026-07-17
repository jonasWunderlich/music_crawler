#!/usr/bin/env python3
import re
import os
import html
import time
import json
import urllib.parse
import urllib.request
from pathlib import Path
import datetime

import questionary
import download_covers

# Configuration
THUMB_DIR = Path("export/thumb")
OUTPUT_DIR = Path("album_covers/org")
LISTS_DIR = Path("lists")
EXPORT_DIR = Path("export")
LEGACY_LINKS_FILE = Path("log/legacy/links.json")
CONFIG_FILE = Path("config.json")

def sanitize_filename(name):
    """Wandelt einen Album-/Künstlernamen in einen sicheren Dateinamen um."""
    return download_covers.sanitize_filename(name)

def parse_tags(text):
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

def get_log_path(tag_date: str) -> Path:
    """Nutzt die Log-Pfad-Logik aus download_covers."""
    return download_covers.get_log_path(tag_date)

def load_data_log(tag_date: str):
    log_file = get_log_path(tag_date)
    if log_file.exists():
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {log_file}: {e}")
            return {}
    return {}

def save_data_log(tag_date: str, log_data: dict):
    log_file = get_log_path(tag_date)
    try:
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving {log_file}: {e}")

def download_missing_covers(missing_covers):
    log_cache = {}
    legacy_log = {}
    legacy_dirty = False
    if download_covers.LEGACY_LOG_FILE.exists():
        try:
            legacy_log = json.loads(download_covers.LEGACY_LOG_FILE.read_text(encoding="utf-8"))
        except:
            pass

    for tags in missing_covers:
        tag_date = tags.get('DATE', '0000')
        album_info = {
            "artist": tags.get('ARTIST'),
            "album": tags.get('ALBUM'),
            "label": tags.get('LABEL'),
            "date": tag_date
        }
        key = f"{album_info['artist']} - {album_info['album']}"
        print(f"Processing: {key}")
        
        if tag_date not in log_cache:
            log_cache[tag_date] = download_covers.load_log(tag_date)
        log_data = log_cache[tag_date]

        ok, source, _ = download_covers.download_cover(album_info, OUTPUT_DIR)
        
        if key in legacy_log:
            del legacy_log[key]
            legacy_dirty = True

        if key not in log_data:
            log_data[key] = {}
        log_data[key]["album_art"] = {
            "status": "success" if ok else "failed",
            "timestamp": time.ctime()
        }
        if ok:
            log_data[key]["album_art"]["source"] = source
        else:
            log_data[key]["album_art"]["reason"] = source
        download_covers.save_log(tag_date, log_data)
    
    if legacy_dirty:
        download_covers.LEGACY_LOG_FILE.write_text(json.dumps(legacy_log, indent=2, ensure_ascii=False), encoding="utf-8")

def fetch_bandcamp_links(artist, album):
    def search(search_artist):
        url = "https://bandcamp.com/api/bcsearch_public_api/1/autocomplete_elastic"
        payload = json.dumps({
            "search_text": f"{search_artist} {album}",
            "search_filter": "a",
            "full_page": False,
            "fan_id": None
        }).encode("utf-8")
        
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0"
        }
        
        links = {
            "ARTIST_LINK": "",
            "ALBUM_LINK": "",
            "VIDEO_LINK": ""
        }
        
        try:
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            resp_data = urllib.request.urlopen(req, timeout=10).read()
            j = json.loads(resp_data)
            results = j.get("auto", {}).get("results", [])
            if results:
                first_res = results[0]
                album_url = first_res.get("item_url_path", "").split("?")[0]
                if album_url and album_url.startswith("http"):
                    links["ALBUM_LINK"] = album_url
                    parsed_uri = urllib.parse.urlparse(album_url)
                    links["ARTIST_LINK"] = f"https://{parsed_uri.netloc}"
                else:
                    artist_url = first_res.get("item_url_root", "").split("?")[0]
                    if artist_url and artist_url.startswith("http"):
                        links["ARTIST_LINK"] = artist_url
        except Exception as e:
            print(f"Warning: Failed to fetch bandcamp links for {search_artist} - {album}: {e}")
            
        return links

    links = search(artist)
    if not links["ALBUM_LINK"] and not links["ARTIST_LINK"] and "," in artist:
        cleaned_artist = artist.split(",")[0].strip()
        print(f"  → Kein Treffer für '{artist}'. Versuche Fallback: '{cleaned_artist}'")
        links = search(cleaned_artist)
        
    return links

def fetch_musicbrainz_data(artist, album):
    import time
    query = urllib.parse.quote(f'artist:"{artist}" AND releasegroup:"{album}"')
    url = f"https://musicbrainz.org/ws/2/release-group/?query={query}&limit=1&fmt=json"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'MusicCrawler/1.0'})
        data = urllib.request.urlopen(req, timeout=10).read()
        j = json.loads(data)
        rgs = j.get("release-groups", [])
        if rgs:
            rg_id = rgs[0].get("id")
            if rg_id:
                time.sleep(1) # Be nice to MusicBrainz rate limits
                url2 = f"https://musicbrainz.org/ws/2/release-group/{rg_id}?fmt=json&inc=url-rels+ratings+genres+annotation"
                req2 = urllib.request.Request(url2, headers={'User-Agent': 'MusicCrawler/1.0'})
                data2 = urllib.request.urlopen(req2, timeout=10).read()
                return json.loads(data2)
    except Exception as e:
        print(f"Warning: Failed to fetch MusicBrainz data for {artist} - {album}: {e}")
    return {}

def get_wikipedia_from_mb(mb_data):
    if not mb_data:
        return ""
    
    relations = mb_data.get("relations", [])
    wikidata_url = ""
    for rel in relations:
        if rel.get("type") == "wikidata":
            url = rel.get("url", {}).get("resource", "")
            if "wikidata.org" in url:
                wikidata_url = url
                break
                
    if not wikidata_url:
        return ""
        
    try:
        qid = wikidata_url.rstrip("/").split("/")[-1]
        api_url = f"https://www.wikidata.org/w/api.php?action=wbgetentities&ids={qid}&props=sitelinks/urls&format=json"
        req = urllib.request.Request(api_url, headers={'User-Agent': 'MusicCrawler/1.0'})
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        sitelinks = data.get("entities", {}).get(qid, {}).get("sitelinks", {})
        if "enwiki" in sitelinks:
            return sitelinks["enwiki"].get("url", "")
    except Exception as e:
        print(f"Warning: Failed to fetch Wikipedia link from Wikidata ({wikidata_url}): {e}")
        
    return ""

def generate_html(input_file, output_file, is_year_file=None, current_year=None, records_content=None, menu_files=None, is_decade_file=False, current_decade=None, all_decades=None, all_years=None):
    config_data = {}
    if CONFIG_FILE.exists():
        try:
            config_data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except:
            pass

    search_musicbrainz = config_data.get("search_musicbrainz", True)
    search_musicbrainz_missing = config_data.get("search_musicbrainz_missing", False)
    search_musicbrainz_full = config_data.get("search_musicbrainz_full", False)
    search_bandcamp = config_data.get("search_bandcamp", True)
    search_bandcamp_missing = config_data.get("search_bandcamp_missing", False)

    if records_content is not None:
        content = records_content
        header_raw = ""
        records_raw = content
    else:
        content = input_file.read_text(encoding="utf-8")
        
        # Identify header (before first TAG_HIDDEN)
        header_end_idx = content.find("TAG_HIDDEN=")
        if header_end_idx == -1:
            print("Error: No TAG_HIDDEN found in file.")
            return []

        header_raw = content[:header_end_idx]
        records_raw = content[header_end_idx:]

    # Determine if it's a year-based file
    if is_year_file is None:
        is_year_file = input_file.stem.isdigit() if input_file else False
    if current_year is None:
        current_year = int(input_file.stem) if (input_file and is_year_file) else None

    # Parse Navigation, Title, and Sort from header_raw
    if is_decade_file:
        auto_nav = []
        auto_nav.append({"type": "link", "label": "Home", "url": "../index.html"})
        if all_decades and current_decade in all_decades:
            idx = all_decades.index(current_decade)
            if idx > 0:
                prev_dec = all_decades[idx - 1]
                auto_nav.append({"type": "link", "label": prev_dec, "url": f"{prev_dec}.html"})
        page_title = f"{current_decade} (Rating >= 7)"
        auto_nav.append({"type": "title", "label": page_title})
        if all_decades and current_decade in all_decades:
            idx = all_decades.index(current_decade)
            if idx < len(all_decades) - 1:
                next_dec = all_decades[idx + 1]
                auto_nav.append({"type": "link", "label": next_dec, "url": f"{next_dec}.html"})
        nav_items = auto_nav
        initial_sort = "TAG_RATING"
        show_date = True
        show_tino_filter = True
        show_wire_filter = True
    elif records_content is not None and is_year_file:
        auto_nav = []
        auto_nav.append({"type": "link", "label": "Home", "url": "../index.html"})
        prev_year = current_year - 1
        if all_years and prev_year in all_years:
            auto_nav.append({"type": "link", "label": str(prev_year), "url": f"{prev_year}.html"})
        page_title = f"Records in {current_year}"
        auto_nav.append({"type": "title", "label": page_title})
        next_year = current_year + 1
        if all_years and next_year in all_years:
            auto_nav.append({"type": "link", "label": str(next_year), "url": f"{next_year}.html"})
        nav_items = auto_nav
        if current_year == datetime.date.today().year:
            initial_sort = "TAG_ADDED"
        else:
            initial_sort = "TAG_RATING"
        show_date = False
        show_tino_filter = True
        show_wire_filter = True
    else:
        nav_items = []
        page_title = "Records"
        if is_year_file and current_year == datetime.date.today().year:
            initial_sort = "TAG_ADDED"
        else:
            initial_sort = "TAG_RATING"
        show_date = False
        show_tino_filter = True
        show_wire_filter = True
        
        parsing_settings = False
        for line in header_raw.splitlines():
            line = line.strip()
            if not line:
                continue
                
            if line.startswith("***"):
                parsing_settings = (line.lower() == "*** settings")
                continue
            
            if parsing_settings:
                if "=" in line:
                    key, val = line.split("=", 1)
                    k = key.strip().upper()
                    v = val.strip()
                    if k == "SORT_LIST_ORDER":
                        initial_sort = v.upper()
                    elif k == "SHOW_DATE":
                        show_date = (v == "1")
                    elif k == "FILTER__TAG_TINO":
                        show_tino_filter = (v != "0")
                    elif k == "FILTER__TAG_WIRE":
                        show_wire_filter = (v != "0")
                else:
                    # Handle direct values for backward compatibility
                    initial_sort = line.upper()
                
                if initial_sort == "DEFAULT":
                    initial_sort = "ORIGINAL"
                # We stay in settings mode until we see NAV or TITEL or empty line
                continue

            if line.startswith("NAV="):
                parts = line[4:].split(",")
                if len(parts) == 2:
                    nav_items.append({"type": "link", "label": parts[0].strip(), "url": parts[1].strip()})
            elif line.startswith("TITEL="):
                page_title = line[6:].strip()
                nav_items.append({"type": "title", "label": page_title})

        # Automate Navigation for year-based files
        if is_year_file:
            auto_nav = []
            auto_nav.append({"type": "link", "label": "Home", "url": "../index.html"})
            
            # Previous Year
            prev_year = current_year - 1
            if (input_file.parent / f"{prev_year}.txt").exists():
                auto_nav.append({"type": "link", "label": str(prev_year), "url": f"{prev_year}.html"})
                
            page_title = f"Records in {current_year}"
            auto_nav.append({"type": "title", "label": page_title})
            
            # Next Year
            next_year = current_year + 1
            if (input_file.parent / f"{next_year}.txt").exists():
                auto_nav.append({"type": "link", "label": str(next_year), "url": f"{next_year}.html"})
                
            nav_items = auto_nav

    # Define Sort UI
    sort_ui = f"""
    <div class="sort-controls">
        <div class="sort-group">
            <button class="sort-button" onclick="sortPosters('rating', this)">Bewertung</button>
            <button class="sort-button" onclick="sortPosters('artist', this)">Artist</button>
            <button class="sort-button" onclick="sortPosters('added', this)">Hinzugefügt</button>
        </div>
        <div class="filter-group">
            {f'<button class="filter-button" data-filter="tino" onclick="toggleFilter(\'tino\', this)">Tino</button>' if show_tino_filter else ''}
            {f'<button class="filter-button" data-filter="wire" onclick="toggleFilter(\'wire\', this)">Wire</button>' if show_wire_filter else ''}
        </div>
    </div>
    """

    # Base header from the first few lines of content (static HTML part)
    # We'll assume the first ~10 lines or lines starting with <!DOCTYPE are the template part
    base_header = ""
    for line in header_raw.splitlines():
        if line.startswith("<!DOCTYPE") or line.startswith("<html") or line.startswith("<head") or line.startswith("<meta") or line.startswith("<link") or line.startswith("<title"):
            base_header += line + "\n"
        if "</head>" in line:
            break
    
    if not base_header:
        base_header = """<!DOCTYPE html>
<html lang=de>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes">
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <link rel="icon" type="image/ico" href="../fav.ico">
    <link rel="stylesheet" href="style-music.css">
</head>
"""

    # Update <title> in base_header
    base_header = re.sub(r'<title>.*?</title>', f'<title>{html.escape(page_title)}</title>', base_header)
    if '<title>' not in base_header:
        base_header = base_header.replace('</head>', f'    <title>{html.escape(page_title)}</title>\n</head>')

    header = base_header

    # Build Navigation HTML
    # Find all HTML files in export directory for the hamburger menu
    if menu_files is not None:
        export_files = menu_files
    else:
        export_files = []
        for f in EXPORT_DIR.glob("*.html"):
            if f.is_file():
                export_files.append(f.name)
        export_files.sort()
    
    menu_links_html = "".join([f'        <a href="{f}">{f.replace(".html", "")}</a>\n' for f in export_files])

    def build_nav(is_footer=False):
        nav = '<nav class="site-nav">\n' if is_footer else '<nav class="site-nav footer">\n'
        for item in nav_items:
            if item["type"] == "link":
                nav += f'        <a href="{item["url"]}">{html.escape(item["label"])}</a>\n'
            else:
                nav += f'        <span class="nav-title">{html.escape(item["label"])}</span>\n'
        
        menu_id = "menuContentFooter" if is_footer else "menuContent"
        btn_id = "hamburgerBtnFooter" if is_footer else "hamburgerBtn"
        menu_style = 'style="bottom: 50px; top: auto;"' if is_footer else ''
        
        nav += f"""
        <div class="hamburger-menu" id="{'hamburgerMenuFooter' if is_footer else 'hamburgerMenu'}">
            <button class="hamburger-btn" id="{btn_id}" onclick="toggleMenu('{menu_id}', '{btn_id}')" title="Open Navigation">
                <span></span>
                <span></span>
                <span></span>
            </button>
            <div class="menu-content" id="{menu_id}" {menu_style}>
                <div class="menu-header">Collection</div>
                {menu_links_html}
            </div>
        </div>
        """
        nav += '    </nav>\n'
        return nav

    nav_html = build_nav(is_footer=False)
    nav_html_bottom = build_nav(is_footer=True)

    # Inject Nav and Controls into header (body section)
    controls_row = f"""
    <div class="controls-row">
        <div class="search-container">
            <input type="text" id="myInput" onkeyup="searchPosters()" placeholder="Search & Filter Records ..">
            <span class="clear-icon" onclick="clearSearch()" title="Clear">✖</span>
        </div>
        {sort_ui}
    </div>
    """

    if "<body>" in header:
        header = header.replace("<body>", "<body>\n" + nav_html + controls_row)
    else:
        header += "<body>\n" + nav_html + controls_row

    # Link to external styles (already in base_header)

    record_blocks = re.split(r'(?=TAG_HIDDEN=)', records_raw)
    
    unique_records = {}
    missing_covers = []

    for idx, block in enumerate(record_blocks):
        block = block.strip()
        if not block: continue
        
        tags = parse_tags(block)
        tags['_original_index'] = idx
        artist = tags.get('ARTIST')
        album = tags.get('ALBUM')
        if not artist or not album:
            continue
        
        added = tags.get('ADDED', '0000-00-00 00:00:00')
        key = (artist.lower().strip(), album.lower().strip())
        
        if key not in unique_records or added > unique_records[key].get('ADDED', '0000-00-00 00:00:00'):
            unique_records[key] = tags

    html_cards = []
    
    data_log_cache = {}
    legacy_dirty = False
    data_dirty_years = set()
    
    # Legacy Links laden
    legacy_links = {}
    if LEGACY_LINKS_FILE.exists():
        try:
            legacy_links = json.loads(LEGACY_LINKS_FILE.read_text(encoding="utf-8"))
        except:
            pass
    
    # Apply initial sort
    if initial_sort == "TAG_RATING":
        sorted_records = sorted(
            unique_records.values(), 
            key=lambda x: (-int(x.get('RATING')) if x.get('RATING', '').isdigit() else 0, x.get('ARTIST', '').lower(), x.get('ALBUM', '').lower())
        )
    elif initial_sort == "TAG_ADDED":
        sorted_records = sorted(unique_records.values(), key=lambda x: x.get('ADDED', '0000-00-00 00:00:00'), reverse=True)
    elif initial_sort == "TAG_ARTIST":
        sorted_records = sorted(
            unique_records.values(), 
            key=lambda x: (x.get('ARTIST', '').lower(), x.get('ALBUM', '').lower())
        )
    else: # Fallback for ORIGINAL or anything else
        sorted_records = sorted(
            unique_records.values(), 
            key=lambda x: x.get('_original_index', 0)
        )
    
    for tags in sorted_records:
        if tags.get('HIDDEN') == '1':
            continue
        artist = tags.get('ARTIST')
        album = tags.get('ALBUM')
        rating = tags.get('RATING', '?')
        label = tags.get('LABEL', '')
        country = tags.get('COUNTRY', '')
        city = tags.get('CITY', '')
        genre = tags.get('GENRE', '')
        style = tags.get('STYLE', '')
        hidden = tags.get('HIDDEN', '0')
        reissue = tags.get('REISSUE', '0')
        own = tags.get('OWN', '0')
        fan = tags.get('FAN', '0')
        added = tags.get('ADDED', '')
        link = tags.get('LINK', '')
        tino = tags.get('TINO', '0')
        wire = tags.get('WIRE', '0')

        tag_date = tags.get('DATE', '3000')
        log_key = f"{artist} - {album}"

        if tag_date not in data_log_cache:
            data_log_cache[tag_date] = load_data_log(tag_date)
        data_log = data_log_cache[tag_date]
        
        current_video_tag = tags.get('VIDEO', '').strip()
        if current_video_tag == '?':
            current_video_tag = ''
            
        current_album_link_tag = tags.get('ALBUM_LINK', '').strip()
        if current_album_link_tag == '?':
            current_album_link_tag = ''

        # Check if cover already exists
        tag_date_cover = tags.get('DATE', '0000')
        thumb_name_cover = f"{sanitize_filename(artist)}--{sanitize_filename(album)}.webp"
        thumb_path_cover = THUMB_DIR / tag_date_cover / thumb_name_cover
        original_name_cover = f"{sanitize_filename(artist)}--{sanitize_filename(album)}.jpg"
        original_path_cover = OUTPUT_DIR / tag_date_cover / original_name_cover
        cover_found = thumb_path_cover.exists() or original_path_cover.exists()

        if log_key not in data_log:
            data_log[log_key] = {}

        # Determine if we need to search Bandcamp links
        needs_bandcamp_search = False
        if search_bandcamp and not cover_found:
            if "links" not in data_log[log_key]:
                if log_key not in legacy_links:
                    needs_bandcamp_search = True
            elif search_bandcamp_missing:
                links_entry = data_log[log_key].get("links", {})
                if not links_entry or (not links_entry.get("ALBUM_LINK") and not links_entry.get("ARTIST_LINK")):
                    needs_bandcamp_search = True

        if "links" not in data_log[log_key]:
            # Zuerst im Legacy-Log nachsehen
            if log_key in legacy_links:
                print(f"Using legacy links for: {log_key}")
                links = legacy_links[log_key]
                # Video-Link aus Textdatei hat Priorität
                if current_video_tag: links["VIDEO_LINK"] = current_video_tag
                if current_album_link_tag: links["ALBUM_LINK"] = current_album_link_tag
                
                data_log[log_key]["links"] = links
                data_dirty_years.add(tag_date)
                
                # Aus Legacy löschen
                del legacy_links[log_key]
                legacy_dirty = True
            else:
                if needs_bandcamp_search:
                    print(f"Fetching links for: {log_key}")
                    links = fetch_bandcamp_links(artist, album)
                    time.sleep(1) # Be nice to Bandcamp avoiding rate limits
                else:
                    links = {"ARTIST_LINK": "", "ALBUM_LINK": "", "VIDEO_LINK": ""}
                
                links["VIDEO_LINK"] = current_video_tag
                if current_album_link_tag:
                    links["ALBUM_LINK"] = current_album_link_tag
                data_log[log_key]["links"] = links
                data_dirty_years.add(tag_date)
        elif needs_bandcamp_search:
            print(f"Fetching missing/new links for: {log_key}")
            links = fetch_bandcamp_links(artist, album)
            time.sleep(1)
            existing_links = data_log[log_key].get("links", {})
            if links.get("ALBUM_LINK"):
                existing_links["ALBUM_LINK"] = links["ALBUM_LINK"]
            if links.get("ARTIST_LINK"):
                existing_links["ARTIST_LINK"] = links["ARTIST_LINK"]
            if current_video_tag:
                existing_links["VIDEO_LINK"] = current_video_tag
            if current_album_link_tag:
                existing_links["ALBUM_LINK"] = current_album_link_tag
            data_log[log_key]["links"] = existing_links
            data_dirty_years.add(tag_date)

        links = data_log[log_key]["links"]
        if current_video_tag and links.get("VIDEO_LINK") != current_video_tag:
            links["VIDEO_LINK"] = current_video_tag
            data_dirty_years.add(tag_date)
        if current_album_link_tag and links.get("ALBUM_LINK") != current_album_link_tag:
            links["ALBUM_LINK"] = current_album_link_tag
            data_dirty_years.add(tag_date)
                
        mb_entry = data_log[log_key].get("musicbrainz")
        needs_mb_search = False
        if search_musicbrainz and not cover_found:
            if search_musicbrainz_full:
                needs_mb_search = True
            elif "musicbrainz" not in data_log[log_key]:
                needs_mb_search = True
            elif (not mb_entry or mb_entry.get("not_found")) and search_musicbrainz_missing:
                needs_mb_search = True

        if search_musicbrainz:
            if needs_mb_search:
                print(f"Fetching MusicBrainz data for: {log_key}")
                mb_data = fetch_musicbrainz_data(artist, album)
                if not mb_data:
                    mb_data = {"not_found": True}
                data_log[log_key]["musicbrainz"] = mb_data
                data_dirty_years.add(tag_date)
                
                wiki_url = get_wikipedia_from_mb(mb_data)
                data_log[log_key]["wikipedia"] = wiki_url
                
                time.sleep(1)
            elif "wikipedia" not in data_log[log_key]:
                mb_data = data_log[log_key].get("musicbrainz", {})
                wiki_url = get_wikipedia_from_mb(mb_data)
                data_log[log_key]["wikipedia"] = wiki_url
                data_dirty_years.add(tag_date)
                if wiki_url:
                    print(f"Found Wikipedia link for: {log_key}")

        links = data_log[log_key]["links"]
        mb_data = data_log[log_key].get("musicbrainz", {})
        artist_link = links.get("ARTIST_LINK", "")
        album_link = links.get("ALBUM_LINK", "")
        video_link = links.get("VIDEO_LINK", "")
        wiki_url = data_log[log_key].get("wikipedia", "")

        thumb_name = f"{sanitize_filename(artist)}--{sanitize_filename(album)}.webp"
        tag_date = tags.get('DATE', '0000')
        thumb_path = THUMB_DIR / tag_date / thumb_name
        
        img_html = ""
        if thumb_path.exists():
            # Da die HTML-Datei jetzt im export/ Ordner liegt, 
            # ist der Pfad zum Thumbnail relativ dazu: thumb/JAHR/name.webp
            img_html = f'<img src="thumb/{tag_date}/{thumb_name}" alt="{html.escape(album)}" loading="lazy">'
        else:
            img_html = f'<div class="no-cover">NO COVER</div>'
            missing_covers.append(tags)

        search_data = f"{artist} {album} {label} {country} {city} {genre} {style}".lower()
        if reissue == '1' or reissue == 'reissue': search_data += " reissue"
        if own == '1' or own == 'own': search_data += " owned"
        if fan == '1' or fan == 'fan': search_data += " favorite fan"
        
        tag_name = "a" if link else "div"
        href_attr = f'href="{html.escape(link)}" target="_blank"' if link else ""
        card = f"""
        <{tag_name} class="album-poster" 
             {href_attr}
             data-search="{html.escape(search_data)}" 
             data-hidden="{hidden}"
             data-artist="{html.escape(artist)}"
             data-album="{html.escape(album)}"
             data-rating="{rating if rating.isdigit() else 0}"
             data-genre="{html.escape(genre)}"
             data-style="{html.escape(style)}"
             data-country="{html.escape(country)}"
             data-city="{html.escape(city)}"
             data-reissue="{reissue}"
             data-own="{own}"
             data-fan="{fan}"
             data-tino="{tino}"
             data-wire="{wire}"
             data-added="{html.escape(added)}">
            {img_html}
            {f'<div class="vinyl-overlay" title="Owned (Vinyl)"></div>' if own in ['1', 'own'] else ''}
            <div class="top-left-icons">
                {f'<a href="{html.escape(video_link)}" target="_blank" class="video-icon" title="Watch Video"></a>' if video_link and video_link.startswith('http') else ''}
                {f'<a href="{html.escape(wiki_url)}" target="_blank" class="wikipedia-icon" title="Wikipedia Article"></a>' if wiki_url and wiki_url.startswith('http') else ''}
            </div>
            <div class="top-right-icons">
                {f'<div class="rating-circle" title="{html.escape(config_data.get("rations", {}).get(str(rating), ""))}">{rating}</div>' if rating.isdigit() and int(rating) > 0 else ''}
            </div>
            <div class="album-overlay">
                <div class="overlay-bookmarks">
                    {f'<div class="bookmark-tino" title="Tino\'s Tip"></div>' if tino in ['1', 'tino'] else ''}
                    {f'<div class="bookmark-wire" title="The Wire"></div>' if wire in ['1', 'wire'] else ''}
                </div>
                <div class="album-artist" title="{html.escape(artist)}">{f'<a href="{html.escape(artist_link)}" target="_blank">{html.escape(artist)}</a>' if artist_link else html.escape(artist)}{f'<span class="inline-icon" title="Fan/Favorite">❤️</span>' if fan in ['1', 'fan'] else ''}</div>
                <div class="album-title" title="{html.escape(album)}">
                    {f'<a href="{html.escape(album_link)}" target="_blank">{html.escape(album)}</a>' if album_link else html.escape(album)}
                    {f'<span class="date-label">({html.escape(tag_date)})</span>' if show_date and tag_date else ''}
                    {f'<span class="inline-icon" title="Reissue">↻</span>' if reissue in ['1', 'reissue'] else ''}
                </div>
                <div class="album-label" title="{html.escape(label)}">{html.escape(label)}</div>
                <div class="album-meta">
                    <div class="location">
                        <div class="album-country" title="{html.escape(country)}">{html.escape(country)}</div>
                        <div class="album-city" title="{html.escape(city)}">{html.escape(city)}</div>
                    </div>
                    <div class="genre">
                        <div class="album-genre" title="{html.escape(genre)}">{html.escape(genre)}</div>
                        <div class="album-style" title="{html.escape(style)}">{html.escape(style)}</div>
                    </div>
                </div>
            </div>
        </{tag_name}>"""
        html_cards.append(card)

    # Map initial sort to JS criteria
    sort_mapping = {
        "TAG_RATING": "rating",
        "TAG_ARTIST": "artist",
        "TAG_ADDED": "added"
    }
    js_criteria = sort_mapping.get(initial_sort, "")
    js_direction = -1 if js_criteria in ['rating', 'added'] else 1

    footer = f"""
    </div> <!-- .poster-wall -->
    {nav_html_bottom}
    <button class="scroll-top-btn" onclick="window.scrollTo({{top: 0, behavior: 'smooth'}})">↑</button>
    <script>
        // Toggle album info visibility
        function toggleInfoVisibility(hide) {{
            if (hide) {{
                document.body.classList.add('hide-info');
                localStorage.setItem('hideAlbumInfo', 'true');
            }} else {{
                document.body.classList.remove('hide-info');
                localStorage.removeItem('hideAlbumInfo');
            }}
        }}

        document.addEventListener('keydown', function(e) {{
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable) {{
                return;
            }}
            if (e.key === 'h' || e.key === 'H') {{
                const isHidden = document.body.classList.contains('hide-info');
                toggleInfoVisibility(!isHidden);
            }}
        }});

        // Restore state on load
        if (localStorage.getItem('hideAlbumInfo') === 'true') {{
            document.body.classList.add('hide-info');
        }}

        window.onscroll = function() {{
            var btn = document.querySelector(".scroll-top-btn");
            if (document.body.scrollTop > 300 || document.documentElement.scrollTop > 300) {{
                btn.style.display = "flex";
            }} else {{
                btn.style.display = "none";
            }}
        }};

        function clearSearch() {{
            var input = document.getElementById("myInput");
            input.value = "";
            searchPosters();
        }}

        function searchPosters() {{
            updateVisibility();
        }}

        function toggleFilter(type, btn) {{
            btn.classList.toggle("active");
            updateVisibility();
        }}

        function updateVisibility() {{  
            var input = document.getElementById("myInput");
            var clearIcon = document.querySelector(".clear-icon");
            var filterText = input.value.toLowerCase();
            
            if (filterText.length > 0) {{
                clearIcon.style.display = "block";
            }} else {{  
                clearIcon.style.display = "none";
            }}

            var btnTino = document.querySelector(".filter-button[data-filter='tino']");
            var btnWire = document.querySelector(".filter-button[data-filter='wire']");
            var filterTino = btnTino ? btnTino.classList.contains("active") : false;
            var filterWire = btnWire ? btnWire.classList.contains("active") : false;

            var posters = document.getElementsByClassName("album-poster");
            for (var i = 0; i < posters.length; i++) {{  
                var p = posters[i];
                var searchData = p.getAttribute("data-search");
                var isTino = (p.getAttribute("data-tino") === '1' || p.getAttribute("data-tino") === 'tino');
                var isWire = (p.getAttribute("data-wire") === '1' || p.getAttribute("data-wire") === 'wire');

                var visible = searchData.includes(filterText);
                
                // AND-Logik für Filter
                if (filterTino && !isTino) visible = false;
                if (filterWire && !isWire) visible = false;

                p.style.display = visible ? "" : "none";
            }}
        }}

        function toggleMenu(menuId, btnId) {{
            var menu = document.getElementById(menuId || "menuContent");
            var btn = document.getElementById(btnId) || document.querySelector(".hamburger-btn");
            if(menu) menu.classList.toggle("show");
            if(btn) btn.classList.toggle("active");
        }}

        // Close menu when clicking outside
        window.addEventListener('click', function(e) {{
            const menus = ["menuContent", "menuContentFooter"];
            const btns = ["hamburgerBtn", "hamburgerBtnFooter"];
            
            for(let i=0; i<menus.length; i++) {{
                var menu = document.getElementById(menus[i]);
                var btn = document.getElementById(btns[i]);
                if (menu && btn && !menu.contains(e.target) && !btn.contains(e.target)) {{
                    menu.classList.remove("show");
                    btn.classList.remove("active");
                }}
            }}
        }});

        let currentSort = {{ criteria: '{js_criteria}', direction: {js_direction} }};

        function sortPosters(criteria, btn) {{
            var wall = document.querySelector(".poster-wall");
            var posters = Array.from(wall.querySelectorAll(".album-poster"));
            if (currentSort.criteria === criteria) {{
                currentSort.direction *= -1;
            }} else {{
                currentSort.criteria = criteria;
                currentSort.direction = (criteria === 'rating' || criteria === 'added') ? -1 : 1;
            }}
            document.querySelectorAll(".sort-button").forEach(b => {{
                b.classList.remove("active");
                b.innerHTML = b.innerHTML.replace(/ [↑↓]$/, "");
            }});
            btn.classList.add("active");
            btn.innerHTML += (currentSort.direction === 1 ? " ↑" : " ↓");
            posters.sort((a, b) => {{
                var valA = a.getAttribute("data-" + criteria);
                var valB = b.getAttribute("data-" + criteria);
                if (criteria === 'rating') {{
                    var cmp = parseInt(valA) - parseInt(valB);
                    if (cmp !== 0) {{
                        return cmp * currentSort.direction;
                    }} else {{
                        var artistA = a.getAttribute("data-artist") || "";
                        var artistB = b.getAttribute("data-artist") || "";
                        var artistCmp = artistA.localeCompare(artistB, 'de', {{sensitivity: 'base'}});
                        if (artistCmp !== 0) return artistCmp;
                        var albumA = a.getAttribute("data-album") || "";
                        var albumB = b.getAttribute("data-album") || "";
                        return albumA.localeCompare(albumB, 'de', {{sensitivity: 'base'}});
                    }}
                }} else {{
                    var cmp = valA.localeCompare(valB, 'de', {{sensitivity: 'base'}});
                    return cmp * currentSort.direction;
                }}
            }});
            posters.forEach(poster => wall.appendChild(poster));
        }}

        window.addEventListener('DOMContentLoaded', () => {{
            if (currentSort.criteria) {{
                const buttons = document.querySelectorAll(".sort-button");
                for (let btn of buttons) {{
                    if (btn.getAttribute("onclick").includes("'" + currentSort.criteria + "'")) {{
                        btn.classList.add("active");
                        btn.innerHTML += (currentSort.direction === 1 ? " ↑" : " ↓");
                        break;
                    }}
                }}
            }}

            // Clipboard Copy on Card Click
            const wall = document.querySelector(".poster-wall");
            if (wall) {{
                wall.addEventListener('click', function(e) {{
                    const poster = e.target.closest('.album-poster');
                    if (!poster) return;

                    // If clicked a sub-link inside the poster (like artist, album, video, wikipedia links)
                    // we allow the link to open normally and do not copy to clipboard.
                    const closestLink = e.target.closest('a');
                    if (closestLink && closestLink !== poster) {{
                        return;
                    }}

                    const artist = poster.getAttribute('data-artist');
                    const album = poster.getAttribute('data-album');
                    if (artist && album) {{
                        const copyText = artist + " - " + album;
                        navigator.clipboard.writeText(copyText).then(() => {{
                            showToast("Kopiert: " + copyText);
                        }}).catch(err => {{
                            console.error('Fehler beim Kopieren:', err);
                        }});
                    }}
                }});
            }}
        }});

        function showToast(message) {{
            let toast = document.getElementById("copy-toast");
            if (!toast) {{
                toast = document.createElement("div");
                toast.id = "copy-toast";
                toast.className = "copy-toast";
                document.body.appendChild(toast);
            }}
            toast.textContent = message;
            
            // Remove show class and trigger layout reflow to restart animation
            toast.classList.remove("show");
            void toast.offsetWidth;
            toast.classList.add("show");
            
            if (window.copyToastTimeout) {{
                clearTimeout(window.copyToastTimeout);
            }}
            window.copyToastTimeout = setTimeout(() => {{
                toast.classList.remove("show");
            }}, 2000);
        }}
    </script>
</body>
</html>
"""

    final_html = header + '\n    <div class="poster-wall">\n' + "\n".join(html_cards) + "\n" + footer
    output_file.write_text(final_html, encoding="utf-8")
    
    if data_dirty_years:
        for year in data_dirty_years:
            save_data_log(year, data_log_cache[year])
    
    if legacy_dirty:
        LEGACY_LINKS_FILE.write_text(json.dumps(legacy_links, indent=4, ensure_ascii=False), encoding="utf-8")
        
    print(f"Success! {len(html_cards)} albums processed. Created {output_file}")
    return missing_covers

def main():
    from collections import defaultdict
    while True:
        # 1. Select Input File
        LISTS_DIR.mkdir(exist_ok=True)
        txt_files = sorted(
            list(LISTS_DIR.glob("*.txt")), 
            reverse=True
        )
        if not txt_files:
            print(f"Error: No *.txt files found (checked root and {LISTS_DIR}).")
            return

        # Map filenames (without .txt) to full Paths
        file_map = {f.stem: f for f in txt_files}
        choices = sorted(list(file_map.keys()), reverse=True) + ["Exit"]

        selected_name = questionary.autocomplete(
            "Which list file would you like to process? (Type year/name, Exit to quit)",
            choices=choices
        ).ask()

        if not selected_name or selected_name == "Exit":
            break

        input_file = file_map[selected_name]
        EXPORT_DIR.mkdir(exist_ok=True)

        if selected_name == "_full":
            print("Processing _full list... This will generate all year and decade pages.")
            content = input_file.read_text(encoding="utf-8")
            header_end_idx = content.find("TAG_HIDDEN=")
            if header_end_idx == -1:
                print("Error: No entries found in _full.txt.")
                continue
            records_raw = content[header_end_idx:]
            blocks = re.split(r'(?=TAG_HIDDEN=)', records_raw)

            years_data = defaultdict(list)
            decades_data = defaultdict(list)

            for block in blocks:
                block = block.strip()
                if not block:
                    continue
                match = re.search(r'TAG_DATE=(\d{4})', block)
                if match:
                    year = match.group(1)
                    years_data[year].append(block)
                    
                    match_rating = re.search(r'TAG_RATING=(\d+)', block)
                    if match_rating:
                        rating = int(match_rating.group(1))
                        if rating >= 7:
                            decade = year[:3] + "0s"
                            decades_data[decade].append(block)

            all_years = sorted([int(y) for y in years_data.keys()])
            all_decades = sorted(list(decades_data.keys()))

            existing_other_htmls = []
            if EXPORT_DIR.exists():
                for f in EXPORT_DIR.glob("*.html"):
                    if f.is_file():
                        stem = f.stem
                        is_yr = stem.isdigit() and len(stem) == 4
                        is_dec = stem.endswith("s") and stem[:-1].isdigit() and len(stem[:-1]) == 4
                        if not is_yr and not is_dec:
                            existing_other_htmls.append(f.name)

            menu_files = sorted(existing_other_htmls) + [f"{d}.html" for d in all_decades] + [f"{y}.html" for y in all_years]

            def run_generation():
                all_missing = []
                for year_str, blocks_list in sorted(years_data.items()):
                    records_content = "\n".join(blocks_list)
                    missing = generate_html(
                        input_file=None,
                        output_file=EXPORT_DIR / f"{year_str}.html",
                        is_year_file=True,
                        current_year=int(year_str),
                        records_content=records_content,
                        menu_files=menu_files,
                        all_years=all_years
                    )
                    all_missing.extend(missing)

                for decade_str, blocks_list in sorted(decades_data.items()):
                    records_content = "\n".join(blocks_list)
                    missing = generate_html(
                        input_file=None,
                        output_file=EXPORT_DIR / f"{decade_str}.html",
                        is_year_file=False,
                        records_content=records_content,
                        menu_files=menu_files,
                        is_decade_file=True,
                        current_decade=decade_str,
                        all_decades=all_decades
                    )
                    all_missing.extend(missing)
                return all_missing

            all_missing = run_generation()

            # Deduplicate missing covers
            unique_missing = []
            seen_missing = set()
            for tags in all_missing:
                key = (tags.get('ARTIST', '').lower().strip(), tags.get('ALBUM', '').lower().strip())
                if key not in seen_missing:
                    seen_missing.add(key)
                    unique_missing.append(tags)

            if unique_missing:
                print(f"\nThere are {len(unique_missing)} albums missing cover art across all years/decades.")
                retry_choice = questionary.confirm("Would you like to try downloading the missing covers now?", default=False).ask()
                if retry_choice:
                    download_missing_covers(unique_missing)
                    print("\nUpdating all HTML files with newly downloaded covers...")
                    run_generation()
        else:
            output_file = EXPORT_DIR / f"{input_file.stem}.html"
            missing_covers = generate_html(input_file, output_file)
            if missing_covers:
                print(f"\nThere are {len(missing_covers)} albums missing cover art.")
                retry_choice = questionary.confirm("Would you like to try downloading the missing covers now?", default=False).ask()
                if retry_choice:
                    download_missing_covers(missing_covers)
                    print("\nUpdating HTML with newly downloaded covers...")
                    generate_html(input_file, output_file)

        print("\n" + "="*40 + "\n") # Visual separator before showing list again

if __name__ == "__main__":
    main()
