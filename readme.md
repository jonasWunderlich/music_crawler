# MusicCrawler

The musiccrawler script is used to transform a exported json file to static html files that represent a beautiful collection of music

## Refactorings

# Logik für Dateinamen von cover überarbeiten.
- replacements in einer externen replacements.json
- replacements für sonderzeichen und internationale zeichen
- replacements für komplizierte artist namen
- replacements für komplizierte alben namen

# Migration der bisherigen covernamen
- alle coverdateien in album_covers/org und export/thumbs in die neue Schreibweise umbenennen

# Build script der statischen seite überarbeiten
- im ordner album_covers/replacements liegen bilder von covern die die bisherigen bilder ersetzen sollen. Nachdem ein cover ersetzt wurde, soll die Bilddatei aus replacements wieder gelöscht werden.
- wenn in der log datei eine url im ALBUM_LINK steht, soll dieser in der albumkachel als link auf dem albumnamen verwendet werden.