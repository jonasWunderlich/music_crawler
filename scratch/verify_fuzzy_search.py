from pathlib import Path
import sys
import os

# Add current directory to path so we can import download_covers
sys.path.append(os.getcwd())

import download_covers
from thefuzz import fuzz

def test_fuzzy_logic():
    print("Testing Fuzzy Logic...")
    artist = "Arnold Schoenberg"
    album = "Verklärte Nacht"
    
    # Test cases
    test_files = [
        "Arnold Schönberg, The Hollywood String Quartet - Verklaerte Nacht, op. 4",
        "Arnold Schoenberg - Verklärte Nacht",
        "Arnold Schoenberg - Transfigured Night",
        "Random Artist - Some Album"
    ]
    
    target = f"{artist} - {album}".lower()
    
    for f in test_files:
        score = fuzz.ratio(target, f.lower())
        print(f"Match: '{target}' vs '{f}' -> Score: {score}")

def test_search_integration():
    print("\nTesting Search Integration...")
    # Create mock directories and files
    mock_local = Path("covers/search_local")
    mock_local.mkdir(parents=True, exist_ok=True)
    
    test_file = mock_local / "Arnold Schönberg - Verklaerte Nacht.jpg"
    test_file.write_text("dummy data")
    
    try:
        found = download_covers.fuzzy_local_search(
            "Arnold Schoenberg", 
            "Verklaerte Nacht", 
            [mock_local], 
            80
        )
        if found:
            print(f"Success! Found: {found}")
        else:
            print("Failed to find file fuzzy.")
    finally:
        # Cleanup
        if test_file.exists():
            test_file.unlink()

if __name__ == "__main__":
    test_fuzzy_logic()
    test_search_integration()
