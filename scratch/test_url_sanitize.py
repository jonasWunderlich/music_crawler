import re

def sanitize_for_url(name: str) -> str:
    # Umlaute
    name = name.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    name = name.replace("Ä", "Ae").replace("Ö", "Oe").replace("Ü", "Ue")
    
    # Alles außer Buchstaben und Zahlen durch Bindestrich ersetzen
    name = re.sub(r'[^a-zA-Z0-9]+', '-', name)
    
    # Mehrfache Bindestriche reduzieren
    name = re.sub(r'-+', '-', name)
    
    # Am Anfang und Ende aufräumen und klein schreiben
    return name.strip("-").lower()

def get_filename(artist, album):
    # Wir nutzen einen Bindestrich als Trenner zwischen Artist und Album
    return f"{sanitize_for_url(artist)}--{sanitize_for_url(album)}.jpg"

# Testfälle
tests = [
    ("The Beatles", "Abbey Road"),
    ("Müller & Söhne", "Highlights 2024!"),
    ("Artist (with parens)", "Album / With Slashes"),
    ("Schöndorf", "Verklärte Nacht")
]

for artist, album in tests:
    print(f"Original: {artist} - {album}")
    print(f"URL-Safe: {get_filename(artist, album)}")
    print("-" * 20)
