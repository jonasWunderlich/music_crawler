#!/usr/bin/env python3
import re
import os
import html
import time
import json
import urllib.parse
import urllib.request
from pathlib import Path

import questionary
import download_covers

# Configuration
THUMB_DIR = Path("export/thumb")
OUTPUT_DIR = Path("album_covers/org")
LISTS_DIR = Path("lists")
EXPORT_DIR = Path("export")
LEGACY_LINKS_FILE = Path("log/legacy/links.json")

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

def get_log_path(tag_date: str, log_type: str = "links") -> Path:
    """Nutzt die Log-Pfad-Logik aus download_covers."""
    return download_covers.get_log_path(tag_date, log_type)

def load_links_log(tag_date: str):
    log_file = get_log_path(tag_date, "links")
    if log_file.exists():
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {log_file}: {e}")
            return {}
    return {}

def save_links_log(tag_date: str, log_data: dict):
    log_file = get_log_path(tag_date, "links")
    try:
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving {log_file}: {e}")

def fetch_bandcamp_links(artist, album):
    query = urllib.parse.quote(f"{artist} {album}")
    search_url = f"https://bandcamp.com/search?q={query}"
    
    links = {
        "ARTIST_LINK": "",
        "ALBUM_LINK": "",
        "VIDEO_LINK": ""
    }
    
    try:
        req = urllib.request.Request(search_url, headers={'User-Agent': 'Mozilla/5.0'})
        html_content = urllib.request.urlopen(req, timeout=10).read().decode('utf-8')
        
        matches = re.findall(r'<div class="itemurl">.*?<a[^>]+href="([^"]+)"', html_content, re.DOTALL)
        if matches:
            first_url = matches[0].strip().split('?')[0]  # Remove parameters
            if '.bandcamp.com' in first_url:
                if '/album/' in first_url or '/track/' in first_url:
                    links["ALBUM_LINK"] = first_url
                    parsed_uri = urllib.parse.urlparse(first_url)
                    links["ARTIST_LINK"] = f"https://{parsed_uri.netloc}"
                else:
                    links["ARTIST_LINK"] = first_url
    except Exception as e:
        print(f"Warning: Failed to fetch bandcamp links for {artist} - {album}: {e}")
        
    return links

def generate_html(input_file, output_file):
    content = input_file.read_text(encoding="utf-8")
    
    # Identify header (before first TAG_HIDDEN)
    header_end_idx = content.find("TAG_HIDDEN=")
    if header_end_idx == -1:
        print("Error: No TAG_HIDDEN found in file.")
        return []

    header_raw = content[:header_end_idx]
    records_raw = content[header_end_idx:]

    # Parse Navigation, Title, and Sort from header_raw
    nav_items = []
    page_title = "Records"
    initial_sort = "ORIGINAL"  # Default fallback
    
    initial_sort = "TAG_RATING"
    show_date = False
    show_tino_filter = True
    show_wire_filter = True
    
    parsing_settings = False
    for line in header_raw.splitlines():
        line = line.strip()
        if not line:
            continue
            
        if line.lower() == "*** settings":
            parsing_settings = True
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
    export_files = sorted([f.name for f in EXPORT_DIR.glob("*.html") if f.is_file()])
    menu_links_html = "".join([f'        <a href="{f}">{f.replace(".html", "")}</a>\n' for f in export_files])

    nav_html = '<nav class="site-nav">\n'
    for item in nav_items:
        if item["type"] == "link":
            nav_html += f'        <a href="{item["url"]}">{html.escape(item["label"])}</a>\n'
        else:
            nav_html += f'        <span class="nav-title">{html.escape(item["label"])}</span>\n'
    
    nav_html += f"""
        <div class="hamburger-menu" id="hamburgerMenu">
            <button class="hamburger-btn" onclick="toggleMenu()" title="Open Navigation">
                <span></span>
                <span></span>
                <span></span>
            </button>
            <div class="menu-content" id="menuContent">
                <div class="menu-header">Collection</div>
                {menu_links_html}
            </div>
        </div>
    """
    nav_html += '    </nav>\n'

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
    
    links_log_cache = {}
    links_dirty_years = set()
    
    # Legacy Links laden
    legacy_links = {}
    legacy_dirty = False
    if LEGACY_LINKS_FILE.exists():
        try:
            legacy_links = json.loads(LEGACY_LINKS_FILE.read_text(encoding="utf-8"))
        except:
            pass
    
    # Apply initial sort
    if initial_sort == "TAG_RATING":
        sorted_records = sorted(
            unique_records.values(), 
            key=lambda x: (int(x.get('RATING')) if x.get('RATING', '').isdigit() else 0, x.get('ADDED', '')), 
            reverse=True
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

        artist = tags.get('ARTIST')
        album = tags.get('ALBUM')
        tag_date = tags.get('DATE', '3000')
        log_key = f"{artist} - {album}"

        if tag_date not in links_log_cache:
            links_log_cache[tag_date] = load_links_log(tag_date)
        links_log = links_log_cache[tag_date]
        
        current_video_tag = tags.get('VIDEO', '').strip()
        if current_video_tag == '?':
            current_video_tag = ''
            
        current_album_link_tag = tags.get('ALBUM_LINK', '').strip()
        if current_album_link_tag == '?':
            current_album_link_tag = ''

        if log_key not in links_log:
            # Zuerst im Legacy-Log nachsehen
            if log_key in legacy_links:
                print(f"Using legacy links for: {log_key}")
                links = legacy_links[log_key]
                # Video-Link aus Textdatei hat Priorität
                if current_video_tag: links["VIDEO_LINK"] = current_video_tag
                if current_album_link_tag: links["ALBUM_LINK"] = current_album_link_tag
                
                links_log[log_key] = links
                links_dirty_years.add(tag_date)
                
                # Aus Legacy löschen
                del legacy_links[log_key]
                legacy_dirty = True
            else:
                print(f"Fetching links for: {log_key}")
                links = fetch_bandcamp_links(artist, album)
                links["VIDEO_LINK"] = current_video_tag
                if current_album_link_tag:
                    links["ALBUM_LINK"] = current_album_link_tag
                links_log[log_key] = links
                links_dirty_years.add(tag_date)
                time.sleep(1) # Be nice to Bandcamp avoiding rate limits
        else:
            links = links_log[log_key]
            # Update video link in cache if the text file has a new one
            if current_video_tag and links.get("VIDEO_LINK") != current_video_tag:
                links["VIDEO_LINK"] = current_video_tag
                links_dirty_years.add(tag_date)
            # Update album link in cache if explicitly provided in text file
            if current_album_link_tag and links.get("ALBUM_LINK") != current_album_link_tag:
                links["ALBUM_LINK"] = current_album_link_tag
                links_dirty_years.add(tag_date)
        
        artist_link = links.get("ARTIST_LINK", "")
        album_link = links.get("ALBUM_LINK", "")
        video_link = links.get("VIDEO_LINK", "")

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
            </div>
            <div class="top-right-icons">
                {f'<div class="rating-circle">{rating}</div>' if rating.isdigit() and int(rating) > 0 else ''}
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
    <button class="scroll-top-btn" onclick="window.scrollTo({{top: 0, behavior: 'smooth'}})">↑</button>
    <script>
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

        function toggleMenu() {{
            var menu = document.getElementById("menuContent");
            menu.classList.toggle("show");
            var btn = document.querySelector(".hamburger-btn");
            btn.classList.toggle("active");
        }}

        // Close menu when clicking outside
        window.addEventListener('click', function(e) {{
            var menu = document.getElementById("menuContent");
            var btn = document.querySelector(".hamburger-btn");
            if (menu && btn && !menu.contains(e.target) && !btn.contains(e.target)) {{
                menu.classList.remove("show");
                btn.classList.remove("active");
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
                var cmp = 0;
                if (criteria === 'rating') {{
                    cmp = parseInt(valA) - parseInt(valB);
                }} else {{
                    cmp = valA.localeCompare(valB, 'de', {{sensitivity: 'base'}});
                }}
                return cmp * currentSort.direction;
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
        }});
    </script>
</body>
</html>
"""

    final_html = header + '\n    <div class="poster-wall">\n' + "\n".join(html_cards) + "\n" + footer
    output_file.write_text(final_html, encoding="utf-8")
    
    if links_dirty_years:
        for year in links_dirty_years:
            save_links_log(year, links_log_cache[year])
    
    if legacy_dirty:
        LEGACY_LINKS_FILE.write_text(json.dumps(legacy_links, indent=4, ensure_ascii=False), encoding="utf-8")
        
    print(f"Success! {len(html_cards)} albums processed. Created {output_file}")
    return missing_covers

def main():
    while True:
        # 1. Select Input File
        LISTS_DIR.mkdir(exist_ok=True)
        txt_files = sorted(
            list(Path(".").glob("_*.txt")) + 
            list(LISTS_DIR.glob("_*.txt")), 
            reverse=True
        )
        if not txt_files:
            print(f"Error: No _*.txt files found (checked root and {LISTS_DIR}).")
            return

        choices = [str(f) for f in txt_files] + ["Exit"]
        input_file_str = questionary.select(
            "Which list file would you like to process?",
            choices=choices
        ).ask()

        if not input_file_str or input_file_str == "Exit":
            break

        input_file = Path(input_file_str)
        # Output file in export/, regardless of where the input file is
        EXPORT_DIR.mkdir(exist_ok=True)
        output_file = EXPORT_DIR / Path(input_file.name[1:].replace(".txt", ".html"))

        missing_covers = generate_html(input_file, output_file)

        # 2. Retry Downloads if needed
        if missing_covers:
            print(f"\nThere are {len(missing_covers)} albums missing cover art.")
            retry_choice = questionary.confirm("Would you like to try downloading the missing covers now?", default=False).ask()
            
            if retry_choice:
                log_cache = {}
                # Legacy Log laden
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
                    
                    # Falls im Legacy-Log, löschen wir ihn (da er nun im neuen Log ist)
                    if key in legacy_log:
                        del legacy_log[key]
                        legacy_dirty = True

                    log_data[key] = {
                        "status": "success" if ok else "failed",
                        "timestamp": time.ctime()
                    }
                    if ok:
                        log_data[key]["source"] = source
                    else:
                        log_data[key]["reason"] = source
                    download_covers.save_log(tag_date, log_data)
                
                if legacy_dirty:
                    download_covers.LEGACY_LOG_FILE.write_text(json.dumps(legacy_log, indent=2, ensure_ascii=False), encoding="utf-8")
                
                # Re-generate HTML after downloads to include new covers
                print("\nUpdating HTML with newly downloaded covers...")
                generate_html(input_file, output_file)
        
        print("\n" + "="*40 + "\n") # Visual separator before showing list again

if __name__ == "__main__":
    main()
