# MusicCrawler

The ***MusicCrawler*** script transforms an exported JSON file into a static HTML site that displays a curated music collection. Prior to building the pages, it extensively crawls external APIs and databases to retrieve rich metadata and high-resolution cover artwork for every record.

## Features

### Album Artwork Retrieval & Processing
* **Multi-Source Fetching:** Downloads album covers from MusicBrainz, Bandcamp, Cover Art Archive, Last.fm API, or the iTunes Search API.
* **Local Override Directory:** Checks a dedicated local folder for existing artwork before attempting external downloads.
* **Forced Replacements:** Placing an image in the local override folder forces the script to replace existing artwork.
* **Image Optimization:** Resizes retrieved covers and automatically converts them to the web-optimized `.webp` format, generating thumbnails for performance.

### Metadata Collection & Processing
* **MusicBrainz Identification:** Matches records against the MusicBrainz database for accurate metadata.
* **External Resource Linking:** Automatically links records to external platforms including Wikipedia, Discogs, YouTube Music, Spotify, Bandcamp, and more.
* **HTML Generation:** Automatically builds static HTML files for the entire album collection.
* **Fuzzy Search:** Enhances artist and title matching using fuzzy search algorithms.
* **Persistent Logging:** Maintains detailed JSON logs of the processing status across runs.

---

## JSON Log File & Metadata Tracking

The script tracks enrichment states and override settings inside a persistent JSON log file:

### Bandcamp Link Resolution
* **`ARTIST_LINK` & `ALBUM_LINK`:** Automatically resolves Bandcamp links (`ARTIST_LINK` is inferred by traversing up the Bandcamp URL hierarchy, often pointing to publisher pages).
* **Manual Overrides:** Both `ARTIST_LINK` and `ALBUM_LINK` can be edited manually in the JSON file to fix incorrect matches.
* **`VIDEO_LINK`:** Populated from the source JSON's video attribute. Manual entries act as overrides.

### Download Tracking (`album_art`)
* Tracks the success or failure status of artwork downloads.
* Allows the script to skip redundant external lookups and downloads on subsequent runs.

### MusicBrainz Integration (`music_brainz`)
* **Retrieved Data:** Extracts Wikipedia links, cover art, and high-quality genre arrays.
* **Popularity Signals:** Utilizes ratings and vote counts to calculate rudimentary popularity metrics.
* **Entity Relationships:** Collects relational data (dependent on record popularity) for future feature developments.

#### The resulting JSON structure looks like this

      "Germs - (GI)": {
        "links": {
            "ARTIST_LINK": "https://feedingtuberecords.bandcamp.com",
            "ALBUM_LINK": "https://feedingtuberecords.bandcamp.com/track/germs-gi",
            "VIDEO_LINK": ""
        },
        "album_art": {
            "status": "success",
            "timestamp": "Wed Apr 29 01:23:15 2026",
            "source": "Local (legacy)"
        },
        "wikipedia": "https://en.wikipedia.org/wiki/GI_(album)",
        "musicbrainz": {
            "disambiguation": "",
            "annotation": null,
            "secondary-type-ids": [],
            "id": "1f66bd0f-4bbe-3eeb-8271-3a43972473ff",
            "rating": {
                "votes-count": 2,
                "value": 4
            },
            "secondary-types": [],
            "primary-type": "Album",
            "first-release-date": "1979-10",
            "title": "(GI)",
            "relations": [
                {
                    "type-id": "a50a1d20-2b20-4d2c-9a29-eb771dd78386",
                    "attribute-values": {},
                    "attributes": [],
                    "end": null,
                    "type": "allmusic",
                    "begin": null,
                    "direction": "forward",
                    "target-type": "url",
                    "source-credit": "",
                    "target-credit": "",
                    "url": {
                        "resource": "https://www.allmusic.com/album/mw0000312385",
                        "id": "c83e7140-c6ba-4cd1-b784-854211b8de0e"
                    },
                    "attribute-ids": {},
                    "ended": false
                },
                {
                    "source-credit": "",
                    "target-credit": "",
                    "attributes": [],
                    "end": null,
                    "type-id": "99e550f3-5ab4-3110-b5b9-fe01d970b126",
                    "attribute-values": {},
                    "direction": "forward",
                    "target-type": "url",
                    "type": "discogs",
                    "begin": null,
                    "ended": false,
                    "url": {
                        "id": "a02bd26b-e391-4484-8724-62ba8161d902",
                        "resource": "https://www.discogs.com/master/38300"
                    },
                    "attribute-ids": {}
                },
                {
                    "target-credit": "",
                    "source-credit": "",
                    "attributes": [],
                    "end": null,
                    "attribute-values": {},
                    "type-id": "38320e40-9f4a-3ae7-8cb2-3f3c9c5d856d",
                    "target-type": "url",
                    "direction": "forward",
                    "type": "other databases",
                    "begin": null,
                    "ended": false,
                    "attribute-ids": {},
                    "url": {
                        "id": "8382d78c-4697-4301-a7ae-0fa57a84515a",
                        "resource": "https://rateyourmusic.com/release/album/germs/_gi_/"
                    }
                },
                {
                    "ended": false,
                    "attribute-ids": {},
                    "url": {
                        "resource": "https://pitchfork.com/reviews/albums/germs-gi/",
                        "id": "54cf9ba6-d737-4c8c-ad41-1dba81b75b81"
                    },
                    "target-credit": "",
                    "source-credit": "",
                    "attribute-values": {},
                    "type-id": "c3ac9c3b-f546-4d15-873f-b294d2c1b708",
                    "end": null,
                    "attributes": [],
                    "type": "review",
                    "begin": null,
                    "target-type": "url",
                    "direction": "forward"
                },
                {
                    "target-credit": "",
                    "source-credit": "",
                    "begin": null,
                    "type": "wikidata",
                    "target-type": "url",
                    "direction": "forward",
                    "attribute-values": {},
                    "type-id": "b988d08c-5d86-4a57-9557-c83b399e3580",
                    "end": null,
                    "attributes": [],
                    "ended": false,
                    "attribute-ids": {},
                    "url": {
                        "id": "096e3f0b-a66e-4522-9800-159860cf420f",
                        "resource": "https://www.wikidata.org/wiki/Q755912"
                    }
                }
            ],
            "genres": [
                {
                    "name": "hardcore punk",
                    "count": 1,
                    "disambiguation": "",
                    "id": "055a6e4d-d929-42ac-ba7a-9d063b254ea5"
                },
                {
                    "name": "punk",
                    "id": "8cc9b280-230b-4a3a-b1e2-8acab0744dd3",
                    "count": 1,
                    "disambiguation": ""
                },
                {
                    "name": "punk rock",
                    "id": "bd7e1d40-43b1-4ba5-97b3-05b891466962",
                    "disambiguation": "",
                    "count": 2
                }
            ],
            "primary-type-id": "f529b476-6e62-324f-b0aa-1f3e33d313fc"
        }
    },


#### What Information Can Be Found in MusicBrainz Relations?

* **AllMusic (`allmusic.com`)**
  * **Ratings:** Official AllMusic Rating and User Ratings *(highest quality user rating and popularity metrics found so far)*.
  * **Streaming & Purchase Links:** Direct links for Amazon search, Spotify, and Apple Music.
  * **Core Metadata:** Release date, duration, genres, styles, recording dates, and recording locations (e.g., recording studios).
  * **Content & Editorial:** Complete tracklists, AllMusic reviews, user reviews, credits, moods, themes, and similar album recommendations.

* **Wikidata (`wikidata.org`)**
  * **Wikipedia Links:** Article URLs across all available languages.
  * **Core Metadata:** Record type, tracklist, and producers.
  * **External Identifiers:** Cross-references including VIAF Cluster ID, GND ID, Album of the Year ID, AllMusic Album ID, BPI ID, Discogs Master ID, Encyclopædia Britannica ID, Freebase ID, MusicBrainz Release Group ID, and Spotify Album ID.

* **Pitchfork (`pitchfork.com`)**
  * Direct links to official album reviews.

* **Discogs (`discogs.com`)**
  * Direct linkage to Master Releases.

* **Rate Your Music (`rateyourmusic.com`)**
  * Release page references *(awaiting official API release)*.

* **Genius (`genius.com`)**
  * Tracklists, reviews, release dates, and linked album/song credits.
  * Direct links to lyrics, including lookup counter metrics.

* **BBC (`bbc.co.uk`)**
  * Links to official BBC music reviews.

* **Musik-Sammler (`musik-sammler.de`)**
  * Regional metadata for the German market, including ratings and popularity metrics.

* **MusicMoz (`musicmoz.org`)**
  * Community-curated album reviews.

* **Spirit of Rock (`spirit-of-rock.com`)**
  * Genre-specific metadata for rock and metal releases.

---

### Odesli / Songlink Integration (`album.link`)

[album.link](https://album.link) (Odesli) is a free service that generates a unified landing page containing links to all major streaming platforms using a Spotify URL, Apple Music URL, or ISRC/UPC code.

**Example API Call:**
```text
[https://album.link/s/](https://album.link/s/){{SPOTIFY_URL}}