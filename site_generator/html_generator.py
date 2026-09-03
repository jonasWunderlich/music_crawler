import html
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .navigation import build_nav_html
from .utils import get_log_path, load_data_log, sanitize_filename, save_data_log
from .external_links import fetch_bandcamp_links, fetch_musicbrainz_data, get_wikipedia_from_mb

def generate_page_html(
    page_type: str,
    page_title: str,
    output_path: Path,
    records: List[Dict[str, Any]],
    config: Dict[str, Any],
    nav_items: List[Dict[str, str]],
    menu_links: List[Dict[str, str]],
    initial_sort: str = "rating",
    initial_sort_direction: str = "desc",
    show_release_year_sort: bool = True,
    show_date_label: bool = False,
    thumb_dir: Path = Path("export/thumb"),
    org_cover_dir: Path = Path("album_covers/org"),
    log_dir: Path = Path("log"),
    enable_external_crawlers: bool = True
) -> List[Dict[str, Any]]:
    """
    Generiert eine statische HTML-Seite für die übergebenen Alben.
    Gibt eine Liste von Alben zurück, für die noch kein Cover vorhanden ist.
    """
    url_crawler_cfg = config.get("urlCrawler", {})
    mb_cfg = url_crawler_cfg.get("musicbrainz", {})
    bc_cfg = url_crawler_cfg.get("bandcamp", {})

    search_mb = enable_external_crawlers and mb_cfg.get("enabled", True)
    search_mb_missing = mb_cfg.get("missing_only", False)
    search_mb_full = mb_cfg.get("full", False)

    search_bc = enable_external_crawlers and bc_cfg.get("enabled", True)
    search_bc_missing = bc_cfg.get("missing_only", False)

    rating_messages = config.get("ratingHoverMesseges") or config.get("ratings") or {}

    # Sortier-Controls HTML
    year_button_html = (
        '            <button class="sort-button" onclick="sortPosters(\'year\', this)">Jahr</button>\n'
        if show_release_year_sort else ''
    )

    sort_ui = f"""
    <div class="sort-controls">
        <div class="sort-group">
            <button class="sort-button" onclick="sortPosters('rating', this)">Bewertung</button>
            <button class="sort-button" onclick="sortPosters('artist', this)">Artist</button>
            <button class="sort-button" onclick="sortPosters('added', this)">Hinzugefügt</button>
{year_button_html}        </div>
        <div class="filter-group">
            <button class="filter-button" data-filter="tino" onclick="toggleFilter('tino', this)">Tino</button>
            <button class="filter-button" data-filter="wire" onclick="toggleFilter('wire', this)">Wire</button>
        </div>
    </div>
"""

    controls_row = f"""
    <div class="controls-row">
        <div class="search-container">
            <input type="text" id="myInput" onkeyup="searchPosters()" placeholder="Search & Filter Records ..">
            <span class="clear-icon" onclick="clearSearch()" title="Clear">✖</span>
        </div>
{sort_ui}
    </div>
"""

    nav_html_top = build_nav_html(nav_items, menu_links, is_footer=False)
    nav_html_bottom = build_nav_html(nav_items, menu_links, is_footer=True)

    header = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes">
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <link rel="icon" type="image/ico" href="../fav.ico">
    <link rel="stylesheet" href="style-music.css">
    <title>{html.escape(page_title)}</title>
</head>
<body>
{nav_html_top}
{controls_row}
"""

    html_cards: List[str] = []
    missing_covers: List[Dict[str, Any]] = []
    data_log_cache: Dict[str, Dict[str, Any]] = {}
    data_dirty_years: Set[str] = set()

    for album in records:
        tag_date = album["releaseYear"]
        display_artist = album["display_artist"]
        sort_artist = album["sort_artist"]
        artist_raw = album["artist"]
        title = album["title"]
        rating_str = album["rating"]
        rating_int = album["rating_int"]
        label = album["label"]
        country = album["country"]
        city = album["city"]
        genre = album["genre"]
        style = album["style"]
        hidden = 1 if album["hidden"] else 0
        reissue = 1 if album["reissue"] else 0
        own = 1 if album["owned"] else 0
        fan = 1 if album["fan"] else 0
        favorite = 1 if album["favorite"] else 0
        tino = 1 if album["tino"] else 0
        wire = 1 if album["wire"] else 0
        added = album["addedDate"]
        video_from_record = album["video"]
        search_text = album["search_text"]
        log_key = album["log_key"]

        if tag_date not in data_log_cache:
            data_log_cache[tag_date] = load_data_log(tag_date, log_dir)
        data_log = data_log_cache[tag_date]

        # Prüfen ob Cover vorhanden ist
        thumb_name = f"{sanitize_filename(display_artist)}--{sanitize_filename(title)}.webp"
        thumb_path = thumb_dir / tag_date / thumb_name
        org_name = f"{sanitize_filename(display_artist)}--{sanitize_filename(title)}.jpg"
        org_path = org_cover_dir / tag_date / org_name
        cover_found = thumb_path.exists() or org_path.exists()

        if log_key not in data_log:
            data_log[log_key] = {}

        # Bandcamp Crawler Check
        needs_bc_search = False
        if search_bc and not cover_found:
            if "links" not in data_log[log_key]:
                needs_bc_search = True
            elif search_bc_missing:
                links_entry = data_log[log_key].get("links", {})
                if not links_entry or (not links_entry.get("ALBUM_LINK") and not links_entry.get("ARTIST_LINK")):
                    needs_bc_search = True

        if needs_bc_search:
            print(f"Suche Bandcamp-Links für: {log_key}")
            bc_links = fetch_bandcamp_links(display_artist, title)
            time.sleep(1)
            existing_links = data_log[log_key].get("links", {})
            if bc_links.get("ALBUM_LINK"):
                existing_links["ALBUM_LINK"] = bc_links["ALBUM_LINK"]
            if bc_links.get("ARTIST_LINK"):
                existing_links["ARTIST_LINK"] = bc_links["ARTIST_LINK"]
            data_log[log_key]["links"] = existing_links
            data_dirty_years.add(tag_date)

        links = data_log[log_key].get("links", {})
        if video_from_record:
            links["VIDEO_LINK"] = video_from_record
            data_log[log_key]["links"] = links

        # MusicBrainz Crawler Check
        mb_entry = data_log[log_key].get("musicbrainz")
        needs_mb_search = False
        if search_mb and not cover_found:
            if search_mb_full:
                needs_mb_search = True
            elif "musicbrainz" not in data_log[log_key]:
                needs_mb_search = True
            elif (not mb_entry or mb_entry.get("not_found")) and search_mb_missing:
                needs_mb_search = True

        if search_mb:
            if needs_mb_search:
                print(f"Suche MusicBrainz-Daten für: {log_key}")
                mb_data = fetch_musicbrainz_data(display_artist, title)
                if not mb_data:
                    mb_data = {"not_found": True}
                data_log[log_key]["musicbrainz"] = mb_data
                wiki_url = get_wikipedia_from_mb(mb_data)
                data_log[log_key]["wikipedia"] = wiki_url
                data_dirty_years.add(tag_date)
                time.sleep(1)
            elif "wikipedia" not in data_log[log_key]:
                mb_data = data_log[log_key].get("musicbrainz", {})
                wiki_url = get_wikipedia_from_mb(mb_data)
                data_log[log_key]["wikipedia"] = wiki_url
                data_dirty_years.add(tag_date)

        artist_link = links.get("ARTIST_LINK", "")
        album_link = links.get("ALBUM_LINK", "")
        video_link = links.get("VIDEO_LINK", "")
        wiki_url = data_log[log_key].get("wikipedia", "")

        # Cover HTML
        if thumb_path.exists():
            img_html = f'<img src="thumb/{tag_date}/{thumb_name}" alt="{html.escape(title)}" loading="lazy">'
        else:
            img_html = '<div class="no-cover">NO COVER</div>'
            missing_covers.append(album)

        # Rating Circle
        tooltip_text = rating_messages.get(str(rating_int), "")
        rating_circle_html = (
            f'<div class="rating-circle" title="{html.escape(tooltip_text)}">{rating_int}</div>'
            if rating_int > 0 else ''
        )

        # Video & Wikipedia Icons
        video_icon_html = (
            f'<a href="{html.escape(video_link)}" target="_blank" class="video-icon" title="Watch Video"></a>'
            if video_link and video_link.startswith('http') else ''
        )
        wiki_icon_html = (
            f'<a href="{html.escape(wiki_url)}" target="_blank" class="wikipedia-icon" title="Wikipedia Article"></a>'
            if wiki_url and wiki_url.startswith('http') else ''
        )

        card = f"""
        <div class="album-poster" 
             data-search="{html.escape(search_text)}" 
             data-hidden="{hidden}"
             data-artist="{html.escape(sort_artist)}"
             data-artist-raw="{html.escape(artist_raw)}"
             data-album="{html.escape(title)}"
             data-rating="{rating_int}"
             data-genre="{html.escape(genre)}"
             data-style="{html.escape(style)}"
             data-country="{html.escape(country)}"
             data-city="{html.escape(city)}"
             data-reissue="{reissue}"
             data-own="{own}"
             data-fan="{fan}"
             data-favorite="{favorite}"
             data-tino="{tino}"
             data-wire="{wire}"
             data-added="{html.escape(added)}"
             data-year="{html.escape(tag_date)}">
            {img_html}
            {f'<div class="vinyl-overlay" title="Owned (Vinyl)"></div>' if own else ''}
            <div class="top-left-icons">
                {video_icon_html}
                {wiki_icon_html}
            </div>
            <div class="top-right-icons">
                {rating_circle_html}
            </div>
            <div class="album-overlay">
                <div class="overlay-bookmarks">
                    {f'<div class="bookmark-tino" title="Tino\'s Tip"></div>' if tino else ''}
                    {f'<div class="bookmark-wire" title="The Wire"></div>' if wire else ''}
                </div>
                <div class="album-artist" title="{html.escape(display_artist)}">
                    {f'<a href="{html.escape(artist_link)}" target="_blank">{html.escape(display_artist)}</a>' if artist_link else html.escape(display_artist)}
                    {f'<span class="inline-icon" title="Fan/Favorite">❤️</span>' if (fan or favorite) else ''}
                </div>
                <div class="album-title" title="{html.escape(title)}">
                    {f'<a href="{html.escape(album_link)}" target="_blank">{html.escape(title)}</a>' if album_link else html.escape(title)}
                    {f'<span class="date-label">({html.escape(tag_date)})</span>' if show_date_label and tag_date else ''}
                    {f'<span class="inline-icon" title="Reissue">↻</span>' if reissue else ''}
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
        </div>"""
        html_cards.append(card)

    # Initial JS sort parameter
    sort_key_normalized = initial_sort.lower().strip()
    if sort_key_normalized in ["rating"]:
        js_criteria = "rating"
    elif sort_key_normalized in ["artist"]:
        js_criteria = "artist"
    elif sort_key_normalized in ["addeddate", "added"]:
        js_criteria = "added"
    elif sort_key_normalized in ["releaseyear", "year"]:
        js_criteria = "year"
    else:
        js_criteria = "rating"

    js_direction = -1 if initial_sort_direction.lower() == "desc" else 1

    footer = f"""
    </div> <!-- .poster-wall -->
{nav_html_bottom}
    <button class="scroll-top-btn" onclick="window.scrollTo({{top: 0, behavior: 'smooth'}})">↑</button>
    <script>
        // Album Info Sichtbarkeit (Taste H)
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
                var searchData = p.getAttribute("data-search") || "";
                var isTino = (p.getAttribute("data-tino") === '1');
                var isWire = (p.getAttribute("data-wire") === '1');

                var visible = searchData.includes(filterText);
                
                if (filterTino && !isTino) visible = false;
                if (filterWire && !isWire) visible = false;

                p.style.display = visible ? "" : "none";
            }}
        }}

        function toggleMenu(menuId, btnId) {{
            var menu = document.getElementById(menuId || "menuContent");
            var btn = document.getElementById(btnId) || document.querySelector(".hamburger-btn");
            if (menu) menu.classList.toggle("show");
            if (btn) btn.classList.toggle("active");
        }}

        window.addEventListener('click', function(e) {{
            const menus = ["menuContent", "menuContentFooter"];
            const btns = ["hamburgerBtn", "hamburgerBtnFooter"];
            
            for (let i = 0; i < menus.length; i++) {{
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
                currentSort.direction = (criteria === 'rating' || criteria === 'added' || criteria === 'year') ? -1 : 1;
            }}
            document.querySelectorAll(".sort-button").forEach(b => {{
                b.classList.remove("active");
                b.innerHTML = b.innerHTML.replace(/ [↑↓]$/, "");
            }});
            if (btn) {{
                btn.classList.add("active");
                btn.innerHTML += (currentSort.direction === 1 ? " ↑" : " ↓");
            }}
            posters.sort((a, b) => {{
                var valA = a.getAttribute("data-" + criteria) || "";
                var valB = b.getAttribute("data-" + criteria) || "";
                if (criteria === 'rating' || criteria === 'year') {{
                    var cmp = parseInt(valA || "0") - parseInt(valB || "0");
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

            const wall = document.querySelector(".poster-wall");
            if (wall) {{
                wall.addEventListener('click', function(e) {{
                    const poster = e.target.closest('.album-poster');
                    if (!poster) return;

                    const closestLink = e.target.closest('a');
                    if (closestLink && closestLink !== poster) {{
                        return;
                    }}

                    const artist = poster.getAttribute('data-artist') || poster.getAttribute('data-artist-raw');
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

    output_path.parent.mkdir(parents=True, exist_ok=True)
    full_html = header + '    <div class="poster-wall">\n' + "\n".join(html_cards) + "\n" + footer
    output_path.write_text(full_html, encoding="utf-8")

    if data_dirty_years:
        for yr in data_dirty_years:
            save_data_log(yr, data_log_cache[yr], log_dir)

    print(f"Seite generiert: {output_path.name} ({len(html_cards)} Alben)")
    return missing_covers
