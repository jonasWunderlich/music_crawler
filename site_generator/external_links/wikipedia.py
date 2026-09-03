import json
import urllib.request
from typing import Any, Dict

def get_wikipedia_from_mb(mb_data: Dict[str, Any]) -> str:
    """Extrahiert einen Wikipedia-Artikel-Link aus den MusicBrainz-Daten via Wikidata."""
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
        # Fallback falls dewiki vorhanden
        if "dewiki" in sitelinks:
            return sitelinks["dewiki"].get("url", "")
    except Exception as e:
        print(f"Warning: Failed to fetch Wikipedia link from Wikidata ({wikidata_url}): {e}")
        
    return ""
