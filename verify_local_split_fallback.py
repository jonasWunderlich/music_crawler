from pathlib import Path
import sys
import shutil
from PIL import Image
import io

# Mock the download_cover function
sys.path.append(str(Path(".").absolute()))
import download_covers

def test_local_split_fallback():
    # 1. Setup
    covers_dir = Path("covers")
    search_local = covers_dir / "search_local"
    search_local.mkdir(parents=True, exist_ok=True)
    
    test_output_dir = Path("test_split_output")
    test_output_dir.mkdir(exist_ok=True)
    
    # We want to search for "Various, Wunderlich" but only have "Various - Album.jpg"
    artist = "Various, Wunderlich"
    album = "SplitAlbum"
    
    # The file we HAVE in search_local
    simplified_artist = "Various"
    filename_we_have = f"{download_covers.sanitize_filename(simplified_artist)} - {download_covers.sanitize_filename(album)}.jpg"
    
    # The filename the script expects if it copies it
    # Wait, if it finds "Various - Album.jpg", it should save it as "Various, Wunderlich - Album.jpg"
    # because that's the canonical filename for THIS album.
    expected_filename = f"{download_covers.sanitize_filename(artist)} - {download_covers.sanitize_filename(album)}.jpg"
    
    # Create a valid JPEG using Pillow
    img = Image.new('RGB', (10, 10), color='green')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    valid_jpeg = img_byte_arr.getvalue()
    
    local_file = search_local / filename_we_have
    local_file.write_bytes(valid_jpeg)
    
    album_info = {"artist": artist, "album": album}
    
    # 2. Execution
    ok, source, returned_filename = download_covers.download_cover(album_info, test_output_dir)
    
    # 3. Verification
    if ok and source == "search_local":
        print(f"✅ SUCCESS: Fallback to split name worked.")
        if (test_output_dir / expected_filename).exists():
            print(f"✅ SUCCESS: File saved as {expected_filename}")
        else:
            print(f"❌ FAILURE: File not found in {test_output_dir} with expected name {expected_filename}")
            # Check what's actually there
            print("Actually there:", [f.name for f in test_output_dir.glob("*")])
            sys.exit(1)
    else:
        print(f"❌ FAILURE: Fallback failed. Success: {ok}, Source: {source}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        test_local_split_fallback()
    finally:
        # Cleanup
        if Path("covers/search_local/Various - SplitAlbum.jpg").exists():
            Path("covers/search_local/Various - SplitAlbum.jpg").unlink()
        if Path("test_split_output").exists():
            shutil.rmtree("test_split_output")
