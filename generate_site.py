#!/usr/bin/env python3
"""
generate_site.py - Hauptprogramm / CLI für den statischen Musik-Webseiten-Generator.
Liest lists/library.json und config.json und generiert alle konfigurierten Seiten.
"""

import argparse
import datetime
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Set

from site_generator.data_loader import load_library
from site_generator.download_covers import download_missing_covers
from site_generator.html_generator import generate_page_html
from site_generator.navigation import (
    get_nav_items_for_decade,
    get_nav_items_for_special,
    get_nav_items_for_year,
)
from site_generator.records import (
    filter_by_decade,
    filter_by_year,
    filter_favorites,
    filter_owned,
    filter_samplers,
    filter_wishlist,
    sort_records,
)
from site_generator.utils import load_config

def main():
    parser = argparse.ArgumentParser(description="Generiert statische Musik-Webseiten aus library.json.")
    parser.add_argument("--config", "-c", type=Path, default=Path("config.json"), help="Pfad zur config.json")
    parser.add_argument("--library", "-l", type=Path, default=None, help="Pfad zur library.json")
    parser.add_argument("--export-dir", "-o", type=Path, default=Path("export"), help="Ausgabeordner für HTML")
    parser.add_argument("--year", "-y", type=str, default=None, help="Nur ein bestimmtes Jahr generieren (z.B. 2026)")
    parser.add_argument("--decade", "-d", type=str, default=None, help="Nur eine bestimmte Dekade generieren (z.B. 2020s)")
    parser.add_argument("--specials-only", action="store_true", help="Nur Sonderseiten generieren")
    parser.add_argument("--no-crawler", action="store_true", help="Externe URL-Crawler (Bandcamp/MusicBrainz) deaktivieren")
    parser.add_argument("--download-covers", action="store_true", help="Fehlende Cover automatisch herunterladen")
    parser.add_argument("--no-input", action="store_true", help="Keine interaktiven Fragen stellen")
    args = parser.parse_args()

    # 1. Konfiguration laden
    config = load_config(args.config)
    pages_cfg = config.get("pages", {})

    # 2. Bibliothek laden
    library_path = args.library or Path(config.get("library_path", "lists/library.json"))
    if not library_path.exists():
        print(f"Fehler: Bibliotheksdatei {library_path} existiert nicht!", file=sys.stderr)
        sys.exit(1)

    all_albums = load_library(library_path)

    # 3. Vorhandene Jahre und Dekaden ermitteln
    years_set = set()
    for album in all_albums:
        yr = album["releaseYear"]
        if yr.isdigit() and len(yr) == 4 and int(yr) > 0:
            years_set.add(int(yr))

    all_years = sorted(list(years_set))
    all_decades = sorted(list(set(f"{str(y)[:3]}0s" for y in all_years)))

    export_dir = args.export_dir
    export_dir.mkdir(parents=True, exist_ok=True)

    # 4. Hamburger-Menü-Einträge vorbereiten
    menu_links: List[Dict[str, str]] = []

    # Sonderseiten im Menü
    special_pages_defs = [
        ("owned", "Meine Platten", "meine-platten.html"),
        ("favorites", "Meine Favoriten", "meine-favoriten.html"),
        ("samplers", "Meine Sampler", "meine-sampler.html"),
        ("wishlist", "Meine Wishlist", "meine-wishlist.html"),
    ]

    for key, def_title, def_filename in special_pages_defs:
        cfg = pages_cfg.get(key, {})
        if cfg.get("enabled", True):
            title = cfg.get("title", def_title)
            filename = cfg.get("filename", def_filename)
            menu_links.append({"label": title, "url": filename})

    # Dekaden im Menü
    if pages_cfg.get("decades", {}).get("enabled", True):
        for dec in all_decades:
            menu_links.append({"label": dec, "url": f"{dec}.html"})

    # Jahre im Menü
    if pages_cfg.get("years", {}).get("enabled", True):
        for yr in all_years:
            menu_links.append({"label": str(yr), "url": f"{yr}.html"})

    current_calendar_year = datetime.date.today().year

    def run_site_generation() -> List[Dict[str, Any]]:
        all_missing: List[Dict[str, Any]] = []

        # --- A: Sonderseiten generieren ---
        if args.year is None and args.decade is None:
            # Meine Platten
            owned_cfg = pages_cfg.get("owned", {})
            if owned_cfg.get("enabled", True):
                title = owned_cfg.get("title", "Meine Platten")
                filename = owned_cfg.get("filename", "meine-platten.html")
                sort_key = owned_cfg.get("sort", "releaseYear")
                sort_dir = owned_cfg.get("sort_direction", "desc")
                include_hidden = owned_cfg.get("include_hidden", False)

                records = filter_owned(all_albums, include_hidden=include_hidden)
                records = sort_records(records, sort_key=sort_key, sort_direction=sort_dir)
                nav = get_nav_items_for_special(title)

                missing = generate_page_html(
                    page_type="special",
                    page_title=title,
                    output_path=export_dir / filename,
                    records=records,
                    config=config,
                    nav_items=nav,
                    menu_links=menu_links,
                    initial_sort=sort_key,
                    initial_sort_direction=sort_dir,
                    show_release_year_sort=True,
                    show_date_label=True,
                    enable_external_crawlers=not args.no_crawler
                )
                all_missing.extend(missing)

            # Meine Favoriten
            fav_cfg = pages_cfg.get("favorites", {})
            if fav_cfg.get("enabled", True):
                title = fav_cfg.get("title", "Meine Favoriten")
                filename = fav_cfg.get("filename", "meine-favoriten.html")
                sort_key = fav_cfg.get("sort", "releaseYear")
                sort_dir = fav_cfg.get("sort_direction", "desc")
                include_hidden = fav_cfg.get("include_hidden", False)

                records = filter_favorites(all_albums, include_hidden=include_hidden)
                records = sort_records(records, sort_key=sort_key, sort_direction=sort_dir)
                nav = get_nav_items_for_special(title)

                missing = generate_page_html(
                    page_type="special",
                    page_title=title,
                    output_path=export_dir / filename,
                    records=records,
                    config=config,
                    nav_items=nav,
                    menu_links=menu_links,
                    initial_sort=sort_key,
                    initial_sort_direction=sort_dir,
                    show_release_year_sort=True,
                    show_date_label=True,
                    enable_external_crawlers=not args.no_crawler
                )
                all_missing.extend(missing)

            # Meine Sampler
            sam_cfg = pages_cfg.get("samplers", {})
            if sam_cfg.get("enabled", True):
                title = sam_cfg.get("title", "Meine Sampler")
                filename = sam_cfg.get("filename", "meine-sampler.html")
                label_query = sam_cfg.get("label", "Wunderliche Tapes")
                sort_key = sam_cfg.get("sort", "releaseYear")
                sort_dir = sam_cfg.get("sort_direction", "desc")
                include_hidden = sam_cfg.get("include_hidden", True)

                records = filter_samplers(all_albums, label_substring=label_query, include_hidden=include_hidden)
                records = sort_records(records, sort_key=sort_key, sort_direction=sort_dir)
                nav = get_nav_items_for_special(title)

                missing = generate_page_html(
                    page_type="special",
                    page_title=title,
                    output_path=export_dir / filename,
                    records=records,
                    config=config,
                    nav_items=nav,
                    menu_links=menu_links,
                    initial_sort=sort_key,
                    initial_sort_direction=sort_dir,
                    show_release_year_sort=True,
                    show_date_label=True,
                    enable_external_crawlers=not args.no_crawler
                )
                all_missing.extend(missing)

            # Meine Wishlist
            wish_cfg = pages_cfg.get("wishlist", {})
            if wish_cfg.get("enabled", True):
                title = wish_cfg.get("title", "Meine Wishlist")
                filename = wish_cfg.get("filename", "meine-wishlist.html")
                sort_key = wish_cfg.get("sort", "releaseYear")
                sort_dir = wish_cfg.get("sort_direction", "desc")
                include_hidden = wish_cfg.get("include_hidden", False)

                records = filter_wishlist(all_albums, include_hidden=include_hidden)
                records = sort_records(records, sort_key=sort_key, sort_direction=sort_dir)
                nav = get_nav_items_for_special(title)

                missing = generate_page_html(
                    page_type="special",
                    page_title=title,
                    output_path=export_dir / filename,
                    records=records,
                    config=config,
                    nav_items=nav,
                    menu_links=menu_links,
                    initial_sort=sort_key,
                    initial_sort_direction=sort_dir,
                    show_release_year_sort=True,
                    show_date_label=True,
                    enable_external_crawlers=not args.no_crawler
                )
                all_missing.extend(missing)

        if args.specials_only:
            return all_missing

        # --- B: Jahres-Seiten generieren ---
        years_cfg = pages_cfg.get("years", {})
        cur_year_cfg = pages_cfg.get("currentYear", {})
        if (years_cfg.get("enabled", True) or args.year is not None) and args.decade is None:
            target_years = [int(args.year)] if args.year is not None else all_years

            for yr in target_years:
                is_cur_year = (yr == current_calendar_year or yr == 2026)
                cfg = cur_year_cfg if is_cur_year and cur_year_cfg.get("enabled", True) else years_cfg

                include_hidden = cfg.get("include_hidden", False)
                sort_key = cfg.get("sort", "addedDate" if is_cur_year else "rating")
                sort_dir = cfg.get("sort_direction", "desc")

                records = filter_by_year(all_albums, yr, include_hidden=include_hidden)
                records = sort_records(records, sort_key=sort_key, sort_direction=sort_dir)
                nav = get_nav_items_for_year(yr, all_years)

                missing = generate_page_html(
                    page_type="year",
                    page_title=f"Records in {yr}",
                    output_path=export_dir / f"{yr}.html",
                    records=records,
                    config=config,
                    nav_items=nav,
                    menu_links=menu_links,
                    initial_sort=sort_key,
                    initial_sort_direction=sort_dir,
                    show_release_year_sort=False,  # Nicht sichtbar auf Jahres-Seiten!
                    show_date_label=False,
                    enable_external_crawlers=not args.no_crawler
                )
                all_missing.extend(missing)

        # --- C: Dekaden-Seiten generieren ---
        decades_cfg = pages_cfg.get("decades", {})
        if (decades_cfg.get("enabled", True) or args.decade is not None) and args.year is None:
            target_decades = [args.decade] if args.decade is not None else all_decades
            min_rating = decades_cfg.get("minimum_rating", 7)
            include_hidden = decades_cfg.get("include_hidden", False)
            sort_key = decades_cfg.get("sort", "rating")
            sort_dir = decades_cfg.get("sort_direction", "desc")

            for dec in target_decades:
                records = filter_by_decade(all_albums, dec, minimum_rating=min_rating, include_hidden=include_hidden)
                records = sort_records(records, sort_key=sort_key, sort_direction=sort_dir)
                nav = get_nav_items_for_decade(dec, all_decades)

                missing = generate_page_html(
                    page_type="decade",
                    page_title=f"{dec} (Rating >= {min_rating})",
                    output_path=export_dir / f"{dec}.html",
                    records=records,
                    config=config,
                    nav_items=nav,
                    menu_links=menu_links,
                    initial_sort=sort_key,
                    initial_sort_direction=sort_dir,
                    show_release_year_sort=True,
                    show_date_label=True,
                    enable_external_crawlers=not args.no_crawler
                )
                all_missing.extend(missing)

        return all_missing

    # Erste Generierungsrunde
    missing_covers = run_site_generation()

    # Fehlende Cover deduplizieren
    unique_missing: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for item in missing_covers:
        key = item["log_key"].lower().strip()
        if key not in seen:
            seen.add(key)
            unique_missing.append(item)

    print("\n" + "=" * 50)
    print("Webseiten-Generierung abgeschlossen!")

    if unique_missing:
        print(f"Es fehlen Cover für {len(unique_missing)} unterschiedliche Alben.")
        do_download = args.download_covers

        if not do_download and not args.no_input and sys.stdin.isatty():
            try:
                ans = input("Möchtest du versuchen, die fehlenden Cover jetzt herunterzuladen? (j/N): ")
                do_download = ans.strip().lower() in ["j", "ja", "y", "yes"]
            except EOFError:
                pass

        if do_download:
            print("\nStarte Download fehlender Cover...")
            download_missing_covers(unique_missing)
            print("\nAktualisiere HTML-Dateien mit den neuen Covern...")
            run_site_generation()
            print("Fertig!")
    else:
        print("Alle benötigten Album-Cover sind vorhanden.")

if __name__ == "__main__":
    main()
