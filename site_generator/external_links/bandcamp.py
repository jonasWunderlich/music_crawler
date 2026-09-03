import json
import urllib.parse
import urllib.request
from typing import Dict

def fetch_bandcamp_links(artist: str, album: str) -> Dict[str, str]:
    """Sucht nach Bandcamp-Links für Künstler und Album."""
    def search(search_artist: str) -> Dict[str, str]:
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
