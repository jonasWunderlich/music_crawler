#!/usr/bin/env python3
"""
Wrapper for site_generator.download_covers.
"""
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from site_generator.download_covers import main

if __name__ == "__main__":
    main()
