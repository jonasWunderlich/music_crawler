import json
import time
import urllib.parse
import urllib.request
from typing import Any, Dict

USER_AGENT = "MusicCrawler/1.0 ( https://github.com/yourusername/musiccrawler ; contact@yourdomain.com )"

def make_mb_request(url, retries=4, backoff_factor=2):
    """
    Führt einen HTTP-Request aus und fängt 503/429/502-Fehler mit Exponential Backoff ab.
    """
    headers = {"User-Agent": USER_AGENT}
    
    for attempt in range(retries):
        try:
            # Sicherheitsabstand einhalten (MusicBrainz verlangt max 1 req/sec)
            time.sleep(1.2)
            
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=12) as response:
                return json.loads(response.read().decode("utf-8"))

        except urllib.error.HTTPError as err:
            if err.code in (503, 429, 502) and attempt < retries - 1:
                wait_time = backoff_factor ** attempt + 1  # 2s, 3s, 5s, ...
                print(f" -> MusicBrainz Rate-Limit/503 (Attempt {attempt + 1}/{retries}). Warte {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise err
        except Exception as exc:
            if attempt < retries - 1:
                time.sleep(2)
            else:
                raise exc
                
    return {}


def fetch_musicbrainz_data(artist, album):
    # Anführungszeichen in Suchbegriffen escapen
    safe_artist = artist.replace('"', '\\"')
    safe_album = album.replace('"', '\\"')
    
    query = urllib.parse.quote(f'artist:"{safe_artist}" AND releasegroup:"{safe_album}"')
    search_url = f"https://musicbrainz.org/ws/2/release-group/?query={query}&limit=1&fmt=json"

    try:
        data = make_mb_request(search_url)
        groups = data.get("release-groups", [])

        if groups:
            group_id = groups[0].get("id")
            if group_id:
                detail_url = (
                    f"https://musicbrainz.org/ws/2/release-group/{group_id}"
                    "?fmt=json&inc=url-rels+ratings+genres+annotation"
                )
                return make_mb_request(detail_url)

    except Exception as exc:
        print(f"Warning: Failed to fetch MusicBrainz data for {artist} - {album}: {exc}")

    return {}