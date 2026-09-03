import html
from typing import Any, Dict, List, Optional

def get_nav_items_for_year(current_year: int, all_years: List[int]) -> List[Dict[str, str]]:
    """Erstellt Navigations-Items für eine Jahres-Seite."""
    nav_items = [
        {"type": "link", "label": "Home", "url": "../index.html"}
    ]
    prev_year = current_year - 1
    if prev_year in all_years:
        nav_items.append({"type": "link", "label": str(prev_year), "url": f"{prev_year}.html"})

    nav_items.append({"type": "title", "label": f"Records in {current_year}"})

    next_year = current_year + 1
    if next_year in all_years:
        nav_items.append({"type": "link", "label": str(next_year), "url": f"{next_year}.html"})

    return nav_items

def get_nav_items_for_decade(current_decade: str, all_decades: List[str]) -> List[Dict[str, str]]:
    """Erstellt Navigations-Items für eine Dekaden-Seite."""
    nav_items = [
        {"type": "link", "label": "Home", "url": "../index.html"}
    ]
    if current_decade in all_decades:
        idx = all_decades.index(current_decade)
        if idx > 0:
            prev_dec = all_decades[idx - 1]
            nav_items.append({"type": "link", "label": prev_dec, "url": f"{prev_dec}.html"})

    page_title = f"{current_decade} (Rating >= 7)"
    nav_items.append({"type": "title", "label": page_title})

    if current_decade in all_decades:
        idx = all_decades.index(current_decade)
        if idx < len(all_decades) - 1:
            next_dec = all_decades[idx + 1]
            nav_items.append({"type": "link", "label": next_dec, "url": f"{next_dec}.html"})

    return nav_items

def get_nav_items_for_special(title: str) -> List[Dict[str, str]]:
    """Erstellt Navigations-Items für eine Sonderseite."""
    return [
        {"type": "link", "label": "Home", "url": "../index.html"},
        {"type": "title", "label": title}
    ]

def build_nav_html(
    nav_items: List[Dict[str, str]],
    menu_links: List[Dict[str, str]],
    is_footer: bool = False
) -> str:
    """
    Rendert das HTML für eine Navigationsleiste inklusive Hamburger-Menü.
    menu_links: Liste von Dictionaries mit 'label' und 'url'.
    """
    nav_class = "site-nav" if is_footer else "site-nav footer"
    nav = f'    <nav class="{nav_class}">\n'

    for item in nav_items:
        if item["type"] == "link":
            nav += f'        <a href="{item["url"]}">{html.escape(item["label"])}</a>\n'
        else:
            nav += f'        <span class="nav-title">{html.escape(item["label"])}</span>\n'

    menu_id = "menuContentFooter" if is_footer else "menuContent"
    btn_id = "hamburgerBtnFooter" if is_footer else "hamburgerBtn"
    wrapper_id = "hamburgerMenuFooter" if is_footer else "hamburgerMenu"
    menu_style = 'style="bottom: 50px; top: auto;"' if is_footer else ""

    menu_links_html = "".join([
        f'        <a href="{m["url"]}">{html.escape(m["label"])}</a>\n'
        for m in menu_links
    ])

    nav += f"""
        <div class="hamburger-menu" id="{wrapper_id}">
            <button class="hamburger-btn" id="{btn_id}" onclick="toggleMenu('{menu_id}', '{btn_id}')" title="Open Navigation">
                <span></span>
                <span></span>
                <span></span>
            </button>
            <div class="menu-content" id="{menu_id}" {menu_style}>
                <div class="menu-header">Collection</div>
{menu_links_html}            </div>
        </div>
    </nav>
"""
    return nav
