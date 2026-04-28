import json
from pathlib import Path

def migrate_logs():
    log_dir = Path("log")
    log_dir.mkdir(exist_ok=True)
    
    # 1. Migrate download_log.json
    dl_log_file = Path("download_log.json")
    if dl_log_file.exists():
        print(f"Migrating {dl_log_file}...")
        try:
            dl_data = json.loads(dl_log_file.read_text(encoding="utf-8"))
            # We don't easily know the year for each album here without parsing the .txt files
            # But we can try to guess from the timestamp or just put them in '0000' or try to match them later
            # Actually, let's just put them in '0000' for now as a fallback
            year_dir = log_dir / "0000"
            year_dir.mkdir(parents=True, exist_ok=True)
            dest = year_dir / "download_status.json"
            if dest.exists():
                 existing = json.loads(dest.read_text(encoding="utf-8"))
                 existing.update(dl_data)
                 dl_data = existing
            dest.write_text(json.dumps(dl_data, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"  -> Migrated to {dest}")
        except Exception as e:
            print(f"  Error migrating download_log: {e}")

    # 2. Migrate links_log.json
    links_log_file = Path("links_log.json")
    if links_log_file.exists():
        print(f"Migrating {links_log_file}...")
        try:
            links_data = json.loads(links_log_file.read_text(encoding="utf-8"))
            year_dir = log_dir / "0000"
            year_dir.mkdir(parents=True, exist_ok=True)
            dest = year_dir / "links.json"
            if dest.exists():
                 existing = json.loads(dest.read_text(encoding="utf-8"))
                 existing.update(links_data)
                 links_data = existing
            dest.write_text(json.dumps(links_data, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"  -> Migrated to {dest}")
        except Exception as e:
            print(f"  Error migrating links_log: {e}")

if __name__ == "__main__":
    migrate_logs()
