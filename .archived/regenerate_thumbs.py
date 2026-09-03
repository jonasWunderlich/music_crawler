import os
from pathlib import Path
from PIL import Image

ORIGINAL_DIR = Path("album_covers/org")
THUMB_DIR = Path("export/thumb")
THUMB_SIZE = 400

def regenerate():
    THUMB_DIR.mkdir(exist_ok=True, parents=True)
    count = 0
    for path in sorted(ORIGINAL_DIR.glob("*.*")):
        if path.is_file() and path.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
            try:
                img = Image.open(path).convert("RGB")
                new_h = round(img.height * THUMB_SIZE / img.width)
                thumb = img.resize((THUMB_SIZE, new_h), Image.LANCZOS)
                thumb_filename = path.stem + ".webp"
                thumb.save(THUMB_DIR / thumb_filename, "WEBP", quality=85)
                count += 1
            except Exception as e:
                print(f"Failed to process {path.name}: {e}")
    print(f"Successfully generated {count} thumbnail(s).")

if __name__ == "__main__":
    regenerate()
