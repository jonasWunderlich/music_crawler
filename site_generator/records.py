from typing import Any, Dict, List, Optional

def filter_by_year(records: List[Dict[str, Any]], year: Any, include_hidden: bool = False) -> List[Dict[str, Any]]:
    """Filtert Alben nach einem bestimmten Erscheinungsjahr."""
    target_year = str(year).strip()
    return [
        r for r in records
        if r["releaseYear"] == target_year and (include_hidden or not r["hidden"])
    ]

def filter_by_decade(
    records: List[Dict[str, Any]],
    decade_str: str,
    minimum_rating: int = 7,
    include_hidden: bool = False
) -> List[Dict[str, Any]]:
    """Filtert Alben für ein Jahrzehnt (z.B. '2020s') mit Mindest-Rating."""
    prefix = decade_str[:3] if len(decade_str) >= 4 else ""
    return [
        r for r in records
        if len(r["releaseYear"]) == 4 and r["releaseYear"].startswith(prefix)
        and r["rating_int"] >= minimum_rating
        and (include_hidden or not r["hidden"])
    ]

def filter_owned(records: List[Dict[str, Any]], include_hidden: bool = False) -> List[Dict[str, Any]]:
    """Filtert Alben für 'Meine Platten' (owned == True)."""
    return [
        r for r in records
        if r["owned"] and (include_hidden or not r["hidden"])
    ]

def filter_favorites(records: List[Dict[str, Any]], include_hidden: bool = False) -> List[Dict[str, Any]]:
    """Filtert Alben für 'Meine Favoriten' (favorite == True)."""
    return [
        r for r in records
        if r["favorite"] and (include_hidden or not r["hidden"])
    ]

def filter_samplers(
    records: List[Dict[str, Any]],
    label_substring: str = "Wunderliche Tapes",
    include_hidden: bool = True
) -> List[Dict[str, Any]]:
    """Filtert Alben für 'Meine Sampler' (Label/Publisher enthält Substring, case-insensitive)."""
    needle = label_substring.lower()
    return [
        r for r in records
        if (needle in r["label"].lower() or any(needle in p.lower() for p in r["publisher"]))
        and (include_hidden or not r["hidden"])
    ]

def filter_wishlist(records: List[Dict[str, Any]], include_hidden: bool = False) -> List[Dict[str, Any]]:
    """Filtert Alben für 'Meine Wishlist' (wishlist == True)."""
    return [
        r for r in records
        if r["wishlist"] and (include_hidden or not r["hidden"])
    ]

def sort_records(
    records: List[Dict[str, Any]],
    sort_key: str = "rating",
    sort_direction: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Sortiert die Liste von Alben nach dem angegebenen Kriterium.
    Kriterien:
      - 'rating': Nach Bewertung
      - 'addedDate' / 'added': Nach Hinzugefügt-Datum
      - 'releaseYear' / 'year': Nach Erscheinungsjahr
      - 'artist': Nach Sortier-Künstler (erster albumArtist oder artist)
    """
    key = sort_key.lower().strip()
    direction = (sort_direction or "").lower().strip()

    if key == "rating":
        is_desc = direction != "asc"
        return sorted(
            records,
            key=lambda x: (
                -x["rating_int"] if is_desc else x["rating_int"],
                x["sort_artist"].lower(),
                x["title"].lower()
            )
        )

    if key in ["addeddate", "added"]:
        is_desc = direction != "asc"
        return sorted(
            records,
            key=lambda x: x["addedDate"],
            reverse=is_desc
        )

    if key in ["releaseyear", "year"]:
        is_desc = direction != "asc"
        def year_val(item):
            y = item["releaseYear"]
            return int(y) if str(y).isdigit() else 0

        return sorted(
            records,
            key=lambda x: (
                -year_val(x) if is_desc else year_val(x),
                x["sort_artist"].lower(),
                x["title"].lower()
            )
        )

    if key == "artist":
        is_desc = direction == "desc"
        return sorted(
            records,
            key=lambda x: (x["sort_artist"].lower(), x["title"].lower()),
            reverse=is_desc
        )

    # Fallback: unverändert zurückgeben
    return list(records)
