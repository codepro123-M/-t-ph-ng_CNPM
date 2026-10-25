"""Validate all backend/frontend/root file hashes without changing any files."""

from pathlib import Path
from AP_DUNG_SUA_5_LOI import verify_sources

if __name__ == "__main__":
    try:
        records = verify_sources(Path(__file__).resolve().parent)
    except (OSError, ValueError, KeyError) as error:
        raise SystemExit("GOI KHONG HOP LE: " + str(error)) from None
    print("GOI HOP LE:", len(records), "tep khop SHA-256.")
