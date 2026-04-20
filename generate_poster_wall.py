#!/usr/bin/env python3
import re
import os
import html
import time
from pathlib import Path

import questionary
import download_covers

# Configuration
THUMB_DIR = Path("covers/thumbs")
OUTPUT_DIR = Path("covers")

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
    
    parsing_sort = False
    for line in header_raw.splitlines():
        line = line.strip()
        if not line:
            continue
            
        if line.lower() == "*** sort":
            parsing_sort = True
            continue
        
        if parsing_sort:
            if "=" in line:
                key, val = line.split("=", 1)
                if key.strip().upper() == "SORT_LIST_ORDER":
                    initial_sort = val.strip().upper()
            else:
                # Handle direct values for backward compatibility
                initial_sort = line.upper()
            
            if initial_sort == "DEFAULT":
                initial_sort = "ORIGINAL"
            parsing_sort = False
            continue

        if line.startswith("NAV="):
            parts = line[4:].split(",")
            if len(parts) == 2:
                nav_items.append({"type": "link", "label": parts[0].strip(), "url": parts[1].strip()})
        elif line.startswith("TITEL="):
            page_title = line[6:].strip()
            nav_items.append({"type": "title", "label": page_title})

    # Define Sort UI
    sort_ui = """
    <div class="sort-controls">
        <button class="sort-button" onclick="sortPosters('rating', this)">Bewertung</button>
        <button class="sort-button" onclick="sortPosters('artist', this)">Artist</button>
        <button class="sort-button" onclick="sortPosters('added', this)">Hinzugefügt</button>
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
    <link rel="icon" type="image/ico" href="fav.ico">
    <link rel="stylesheet" href="style-music.css">
</head>
"""

    # Update <title> in base_header
    base_header = re.sub(r'<title>.*?</title>', f'<title>{html.escape(page_title)}</title>', base_header)
    if '<title>' not in base_header:
        base_header = base_header.replace('</head>', f'    <title>{html.escape(page_title)}</title>\n</head>')

    header = base_header

    # Build Navigation HTML
    nav_html = '<nav class="site-nav">\n'
    for item in nav_items:
        if item["type"] == "link":
            nav_html += f'        <a href="{item["url"]}">{html.escape(item["label"])}</a>\n'
        else:
            nav_html += f'        <span class="nav-title">{html.escape(item["label"])}</span>\n'
    nav_html += '    </nav>\n'

    # Inject Nav and Controls into header (body section)
    controls_row = f"""
    <div class="controls-row">
        <input type="text" id="myInput" onkeyup="searchPosters()" placeholder="Search & Filter Records ..">
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

        thumb_name = f"{sanitize_filename(artist)} - {sanitize_filename(album)}.webp"
        thumb_path = THUMB_DIR / thumb_name
        
        img_html = ""
        if thumb_path.exists():
            img_html = f'<img src="covers/thumbs/{thumb_name}" alt="{html.escape(album)}" loading="lazy">'
        else:
            img_html = f'<div class="no-cover">NO COVER<br>{html.escape(artist)}<br>{html.escape(album)}</div>'
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
             data-added="{html.escape(added)}">
            {img_html}
            {f'<div class="link-watermark">🔗</div>' if link else ''}
            <div class="tag-icons">
                {f'<span class="tag-icon own-circle" title="Owned"></span>' if own in ['1', 'own'] else ''}
                {f'<span class="tag-icon" title="Reissue">↻</span>' if reissue in ['1', 'reissue'] else ''}
                {f'<span class="tag-icon" title="Fan/Favorite">❤️</span>' if fan in ['1', 'fan'] else ''}
            </div>
            <div class="album-overlay">
                <div class="album-artist" title="{html.escape(artist)}">{html.escape(artist)}</div>
                <div class="album-title" title="{html.escape(album)}">{html.escape(album)}</div>
                <div class="album-label" title="{html.escape(label)}">{html.escape(label)}</div>
                <div class="album-meta">
                    <div class="location">
                        <div class="album-country" title="{html.escape(country)}">{html.escape(country)}</div>
                        <div class="album-city" title="{html.escape(city)}">{html.escape(city)}</div>
                    </div>
                    <span class="rating">{"★" * (int(rating) if rating.isdigit() else 0)}<span class="empty-star">{"☆" * (10 - int(rating) if rating.isdigit() else 0)}</span></span>
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
    <script>
        function searchPosters() {{
            var input = document.getElementById("myInput");
            var filter = input.value.toLowerCase();
            var posters = document.getElementsByClassName("album-poster");
            
            for (var i = 0; i < posters.length; i++) {{
                var searchData = posters[i].getAttribute("data-search");
                if (searchData.includes(filter)) {{
                    posters[i].style.display = "";
                }} else {{
                    posters[i].style.display = "none";
                }}
            }}
        }}

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
    print(f"Success! {len(html_cards)} albums processed. Created {output_file}")
    return missing_covers

def main():
    while True:
        # 1. Select Input File
        txt_files = sorted(list(Path(".").glob("_*.txt")), reverse=True)
        if not txt_files:
            print("Error: No _*.txt files found.")
            return

        choices = [f.name for f in txt_files] + ["Exit"]
        input_file_str = questionary.select(
            "Which list file would you like to process?",
            choices=choices
        ).ask()

        if not input_file_str or input_file_str == "Exit":
            break

        input_file = Path(input_file_str)
        output_file = Path(input_file_str[1:].replace(".txt", ".html"))

        missing_covers = generate_html(input_file, output_file)

        # 2. Retry Downloads if needed
        if missing_covers:
            print(f"\nThere are {len(missing_covers)} albums missing cover art.")
            retry_choice = questionary.confirm("Would you like to try downloading the missing covers now?", default=False).ask()
            
            if retry_choice:
                log_data = download_covers.load_log()
                for tags in missing_covers:
                    album_info = {
                        "artist": tags.get('ARTIST'),
                        "album": tags.get('ALBUM'),
                        "label": tags.get('LABEL')
                    }
                    key = f"{album_info['artist']} - {album_info['album']}"
                    print(f"Processing: {key}")
                    ok, source, _ = download_covers.download_cover(album_info, OUTPUT_DIR)
                    
                    log_data[key] = {
                        "status": "success" if ok else "failed",
                        "timestamp": time.ctime()
                    }
                    if ok:
                        log_data[key]["source"] = source
                    else:
                        log_data[key]["reason"] = source
                    download_covers.save_log(log_data)
                
                # Re-generate HTML after downloads to include new covers
                print("\nUpdating HTML with newly downloaded covers...")
                generate_html(input_file, output_file)
        
        print("\n" + "="*40 + "\n") # Visual separator before showing list again

if __name__ == "__main__":
    main()
