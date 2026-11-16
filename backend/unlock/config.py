"""Runtime configuration (paths only; no secrets are required to run UNLOCK)."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(os.environ.get("UNLOCK_ROOT", Path(__file__).resolve().parents[2]))
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
NORMALIZED_DIR = DATA_DIR / "normalized"
MANIFEST_PATH = DATA_DIR / "manifest" / "sources.json"
STORE_PATH = Path(os.environ.get("UNLOCK_STORE", ROOT / "database" / "unlock.rl"))
BACKUP_DIR = ROOT / "database" / "backups"
# Île-de-France départements (INSEE prefixes) — the pilot boundary.
IDF_DEPARTEMENTS = ("75", "77", "78", "91", "92", "93", "94", "95")
