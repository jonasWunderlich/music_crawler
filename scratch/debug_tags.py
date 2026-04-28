import re
from typing import Dict

def parse_tags(text: str) -> Dict[str, str]:
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

test_line = "TAG_HIDDEN=0 TAG_REISSUE=0 TAG_FAN=0 TAG_OWN=0 TAG_TINO=0 TAG_WIRE=0 TAG_RATING= TAG_DATE=1950 TAG_ARTIST=Arnold Schönberg, The Hollywood String Quartet TAG_ALBUM=Verklaerte Nacht, op. 4 TAG_LABEL=Testament TAG_COUNTRY=US TAG_CITY=Los Angeles, CA TAG_GENRE=Classical TAG_STYLE=Classical TAG_ADDED=2026-04-27 09:26:43 TAG_VIDEO=?"

tags = parse_tags(test_line)
print(f"Extracted Tags: {tags}")
print(f"DATE: {tags.get('DATE')}")
