import json

# Dateipfade anpassen
INPUT_FILE = "lists/library.json"
OUTPUT_FILE = "export/library_normalized.json"

# Die genauen Feldnamen, wie sie in deinem JSON existieren
# (In deinem vorherigen JS-Code hießen sie im Plural: genres, styles, labels, albumArtists)
FIELDS_TO_NORMALIZE = ["genre", "style", "publisher", "albumArtist"]

def main():
    print(f"Lese {INPUT_FILE} ein...")
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        albums = json.load(f)

    # Speicher für unsere Mappings: name -> id
    # z.B. mappings["genres"]["Techno"] = 1
    mappings = {field: {} for field in FIELDS_TO_NORMALIZE}

    # Zähler für fortlaufende IDs
    id_counters = {field: 1 for field in FIELDS_TO_NORMALIZE}

    # 1. Alben durchgehen und Arrays durch IDs ersetzen
    for album in albums:
        for field in FIELDS_TO_NORMALIZE:
            # Prüfen ob das Feld existiert und eine Liste ist
            if field in album and isinstance(album[field], list):
                new_id_list = []

                for item in album[field]:
                    if not isinstance(item, str):
                        continue

                    item_clean = item.strip()
                    if not item_clean:
                        continue

                    # Wenn der Eintrag noch keine ID hat, neue vergeben
                    if item_clean not in mappings[field]:
                        mappings[field][item_clean] = id_counters[field]
                        id_counters[field] += 1

                    # ID zur neuen Liste hinzufügen
                    new_id_list.append(mappings[field][item_clean])

                # Originale String-Liste durch ID-Liste überschreiben
                album[field] = new_id_list

    # 2. Neues Ausgabe-Objekt bauen
    # Wir wandeln das Dictionary (Name->ID) in eine saubere Liste von Objekten um
    output_data = {}

    for field in FIELDS_TO_NORMALIZE:
        entity_list = [{"id": uid, "name": name} for name, uid in mappings[field].items()]
        output_data[field] = entity_list

    # Die angepassten Alben als letztes anhängen
    output_data["albums"] = albums

    # 3. Speichern
    print(f"Speichere in {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    # Statistik ausgeben
    print("\n--- Normalisierung erfolgreich ---")
    for field in FIELDS_TO_NORMALIZE:
        print(f"[{field}]: {len(mappings[field])} eindeutige Einträge erstellt.")
    print(f"[albums]: {len(albums)} Alben verarbeitet.")

if __name__ == "__main__":
    main()