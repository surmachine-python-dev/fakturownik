from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from fakturownik.config import AppPaths, get_app_paths
from fakturownik.database import engine


MANIFEST_NAME = "manifest.json"
DB_ARCNAME = "data/fakturownik.db"
ATTACHMENTS_PREFIX = "attachments/"


def export_backup(target_zip: Path, paths: AppPaths | None = None) -> Path:
    paths = paths or get_app_paths()
    target_zip.parent.mkdir(parents=True, exist_ok=True)

    manifest = {
        "format_version": 1,
        "created_at": datetime.utcnow().isoformat(timespec="seconds"),
        "database": DB_ARCNAME,
        "attachments_dir": ATTACHMENTS_PREFIX,
    }

    with ZipFile(target_zip, "w", compression=ZIP_DEFLATED) as archive:
        if paths.database_path.exists():
            archive.write(paths.database_path, DB_ARCNAME)

        if paths.attachments_dir.exists():
            for file_path in paths.attachments_dir.rglob("*"):
                if file_path.is_file():
                    relative_path = file_path.relative_to(paths.attachments_dir)
                    archive.write(file_path, f"{ATTACHMENTS_PREFIX}{relative_path.as_posix()}")

        archive.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2))

    return target_zip


def import_backup(source_zip: Path, paths: AppPaths | None = None) -> None:
    paths = paths or get_app_paths()
    engine.dispose()
    temp_dir = paths.base_dir / "_restore_tmp"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        with ZipFile(source_zip, "r") as archive:
            archive.extractall(temp_dir)

        manifest_path = temp_dir / MANIFEST_NAME
        if not manifest_path.exists():
            raise ValueError("Backup nie zawiera pliku manifest.json")

        with manifest_path.open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)
        if manifest.get("format_version") != 1:
            raise ValueError("Nieobslugiwany format backupu")

        extracted_db = temp_dir / DB_ARCNAME
        extracted_attachments = temp_dir / ATTACHMENTS_PREFIX.rstrip("/")

        if extracted_db.exists():
            shutil.copy2(extracted_db, paths.database_path)

        if paths.attachments_dir.exists():
            shutil.rmtree(paths.attachments_dir)
        paths.attachments_dir.mkdir(parents=True, exist_ok=True)

        if extracted_attachments.exists():
            shutil.copytree(extracted_attachments, paths.attachments_dir, dirs_exist_ok=True)
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)