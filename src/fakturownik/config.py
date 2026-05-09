from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


APP_NAME = "Fakturownik"


@dataclass(frozen=True)
class AppPaths:
    base_dir: Path
    database_path: Path
    attachments_dir: Path
    backup_dir: Path


def get_app_paths() -> AppPaths:
    local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    base_dir = local_app_data / APP_NAME
    database_path = base_dir / "fakturownik.db"
    attachments_dir = base_dir / "attachments"
    backup_dir = base_dir / "backups"

    for path in (base_dir, attachments_dir, backup_dir):
        path.mkdir(parents=True, exist_ok=True)

    return AppPaths(
        base_dir=base_dir,
        database_path=database_path,
        attachments_dir=attachments_dir,
        backup_dir=backup_dir,
    )