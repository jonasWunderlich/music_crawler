#!/usr/bin/env python3
import re
from pathlib import Path
from collections import defaultdict

# Path configuration
LISTS_DIR = Path("lists")
FULL_LIST_FILE = LISTS_DIR / "_full.txt"

def main():
    if not FULL_LIST_FILE.exists():
        print(f"Error: The file {FULL_LIST_FILE} does not exist.")
        return

    print(f"Reading {FULL_LIST_FILE}...")
    
    # Read and group entries from _full.txt by year
    year_data = defaultdict(list)
    total_entries = 0
    
    with open(FULL_LIST_FILE, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            
            # We only process valid tag lines starting with TAG_HIDDEN=
            if not stripped.startswith("TAG_HIDDEN="):
                continue
                
            # Find the year in TAG_DATE=YYYY
            match = re.search(r'TAG_DATE=(\d{4})', stripped)
            if match:
                year = match.group(1)
                year_data[year].append(stripped)
                total_entries += 1
            else:
                # Fallback check if it's a list item but has no 4-digit date tag
                print(f"Warning: No valid TAG_DATE found in line: {stripped[:100]}...")

    print(f"Loaded {total_entries} entries for {len(year_data)} different years from {FULL_LIST_FILE.name}.")

    # Find all YYYY.txt files in lists/ (where YYYY is a 4-digit number)
    year_files = []
    for path in LISTS_DIR.glob("*.txt"):
        if path.stem.isdigit() and len(path.stem) == 4:
            year_files.append(path)
            
    # Sort files chronologically
    year_files.sort()

    if not year_files:
        print("No YYYY.txt files found in the 'lists/' directory.")
        return

    print(f"Found {len(year_files)} year files to update.")
    print("-" * 50)

    updated_count = 0
    for file_path in year_files:
        year = file_path.stem
        
        # Read the existing file to preserve settings/header
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"Error reading {file_path.name}: {e}")
            continue
            
        # Locate the "*** Liste" section
        liste_idx = content.find("*** Liste")
        if liste_idx == -1:
            print(f"Warning: '*** Liste' section not found in {file_path.name}. Skipping file.")
            continue
            
        # The header is everything up to the "*** Liste" line, plus the line itself and spacing
        # Let's find the end of the "*** Liste" line
        newline_idx = content.find("\n", liste_idx)
        if newline_idx != -1:
            header = content[:newline_idx + 1]
        else:
            header = content[:liste_idx] + "*** Liste\n"
            
        # Ensure there is exactly one empty line after *** Liste, like in the existing templates
        if not header.endswith("\n\n"):
            header += "\n"
            
        # Get the lines for this specific year
        lines_for_year = year_data.get(year, [])
        
        # Join lines with newlines and add a trailing newline
        new_list_content = "\n".join(lines_for_year)
        if new_list_content:
            new_list_content += "\n"
        else:
            print(f"Warning: No entries found in {FULL_LIST_FILE.name} for year {year}. Overwriting with empty list.")

        new_file_content = header + new_list_content
        
        # Write back to file
        try:
            file_path.write_text(new_file_content, encoding="utf-8")
            print(f"Updated {file_path.name}: wrote {len(lines_for_year)} entries.")
            updated_count += 1
        except Exception as e:
            print(f"Error writing to {file_path.name}: {e}")

    print("-" * 50)
    print(f"Done! Successfully updated {updated_count} files.")
    
    # Check if there are any years in _full.txt that do not have a YYYY.txt file
    skipped_years = []
    existing_years = {f.stem for f in year_files}
    for year in sorted(year_data.keys()):
        if year not in existing_years:
            # Check if this year is before the individual year list (usually < 1944)
            # which are grouped in 1920s.txt / 1930s.txt
            skipped_years.append(year)
            
    if skipped_years:
        print(f"Note: The following years were in {FULL_LIST_FILE.name} but skipped because no lists/YEAR.txt exists:")
        print(", ".join(skipped_years))

if __name__ == "__main__":
    main()
