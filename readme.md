# MusicCrawler

The musiccrawler script is used to transform a exported json file to static html files that represent a beautiful collection of music

## Features

* Download album covers from MusicBrainz + Cover Art Archive, Last.fm API, or iTunes Search API
* Download additional metadata from MusicBrainz + Cover Art Archive, Last.fm API, or iTunes Search API
* Link to external resources like Wikipedia, Discogs, YouTube Music, Spotify, Bandcamp, etc.
* Create thumbnails for album covers
* Generate HTML files for albums
* Support for fuzzy search
* Support for persistent logging

## Open Refactorings

### Logic for cover filenames.
- replacements in external replacements.json
- replacements for special characters and international characters
- replacements for complicated artist names
- replacements for complicated album names

### Migration of existing cover filenames
- rename existing cover filesin album_covers/org and export/thumbs and use updated naming

### Build script der statischen seite überarbeiten
- in folder album_covers/replacements there are images of covers that should replace the existing images. After a cover has been replaced, the image file from replacements should be deleted again.
- if in the log for the album there is a url at ALBUM_LINK, it should be used as a link in the album tile on the album name.