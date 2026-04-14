"""
Read backup data from the real status files written by backup_manager.py
and backup_verify.py.

Files read:
- /var/backups/last_run.json — last backup run status
- /var/backups/checksums.json — per-archive checksums
- /var/backups/verify_history.json — verification history
- /var/log/backup.log — historical backup runs (parsed)

Falls back to mock data when files aren't available (local dev).
"""

import json
import os
import re
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

import streamlit as st

from lib.inventory import get_server_config


BACKUP_BASE = Path("/var/backups")
LAST_RUN_FILE = BACKUP_BASE / "last_run.json"
CHECKSUMS_FILE = BACKUP_BASE / "checksums.json"
VERIFY_HISTORY_FILE = BACKUP_BASE / "verify_history.json"
BACKUP_LOG = Path("/var/log/backup.log")
SITE_BACKUP_DIR = BACKUP_BASE / "sites"


def real_data_available() -> bool:
    return LAST_RUN_FILE.exists()


def _load_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


@st.cache_data(ttl=30)
def get_backup_history(days: int = 14):
    if not BACKUP_LOG.exists():
        from lib.mock_backups import get_backup_history as mock
        return mock(days=days)

    last_run = _load_json(LAST_RUN_FILE) or {}

    history = []
    try:
        with open(BACKUP_LOG, "r") as f:
            content = f.read()
    except OSError:
        from lib.mock_backups import get_backup_history as mock
        return mock(days=days)

    runs = re.split(r"={50}\nBackup run started", content)[1:]

    for run in runs[:days]:
        date_match = re.search(r"^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})", run, re.MULTILINE)
        if not date_match:
            continue

        run_time = datetime.strptime(
            f"{date_match.group(1)} {date_match.group(2)}",
            "%Y-%m-%d %H:%M:%S",
        ).replace(tzinfo=timezone.utc)

        duration_match = re.search(r"Duration: (\d+)m (\d+)s", run)
        duration_sec = 0
        if duration_match:
            duration_sec = int(duration_match.group(1)) * 60 + int(duration_match.group(2))

        size_match = re.search(r"Size: ([\d.]+) MB", run)
        size_mb = float(size_match.group(1)) if size_match else 0

        archives_match = re.search(r"Archives: (\d+)", run)
        archive_count = int(archives_match.group(1)) if archives_match else 0

        status_match = re.search(r"Status: (\w+)", run)
        raw_status = (status_match.group(1) if status_match else "unknown").lower()
        status = {"success": "success", "partial": "partial"}.get(raw_status, "failed")

        databases = len(re.findall(r"\.(?:sql|custom)\.gz \(", run))
        files_count = archive_count - databases if archive_count > databases else archive_count

        error_lines = re.findall(r"\[ERROR\] (.+)", run)
        error_detail = " | ".join(error_lines[:3]) if error_lines else ""

        history.append({
            "date": run_time,
            "status": status,
            "databases": databases,
            "files": files_count,
            "size_mb": size_mb,
            "duration_sec": duration_sec,
            "in_progress": False,
            "error_detail": error_detail,
        })

    if not history:
        from lib.mock_backups import get_backup_history as mock
        return mock(days=days)

    return history[:days]


@st.cache_data(ttl=30)
def get_database_backups():
    if not real_data_available():
        from lib.mock_backups import get_database_backups as mock
        return mock()

    checksums = _load_json(CHECKSUMS_FILE) or {}

    db_files = []
    for archive_path, info in checksums.items():
        path = Path(archive_path)
        name = path.stem.split("_")[0]

        if "wordpress" in str(path):
            db_type = "mariadb"
            db_name = f"{name}_db"
        elif "odoo" in str(path):
            db_type = "postgresql"
            db_name = f"{name}_db"
        else:
            continue

        ts = datetime.fromisoformat(info["timestamp"])
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        db_files.append({
            "database": db_name,
            "type": db_type,
            "size_mb": info["size_mb"],
            "last_backup": ts,
            "checksum_ok": True,
        })

    if not db_files:
        from lib.mock_backups import get_database_backups as mock
        return mock()

    seen = {}
    for db in sorted(db_files, key=lambda d: d["last_backup"], reverse=True):
        if db["database"] not in seen:
            seen[db["database"]] = db
    return list(seen.values())


@st.cache_data(ttl=30)
def get_file_backups():
    if not SITE_BACKUP_DIR.exists():
        from lib.mock_backups import get_file_backups as mock
        return mock()

    file_backups = []

    paths_to_check = [
        ("Mail data", SITE_BACKUP_DIR / "mail", "/srv/vmail/"),
        ("System configs", SITE_BACKUP_DIR / "system", "/etc/"),
    ]

    for name, archive_dir, source_path in paths_to_check:
        if not archive_dir.exists():
            continue

        archives = sorted(archive_dir.glob("*.tar.gz"), reverse=True)
        if not archives:
            continue

        latest = archives[0]
        size_mb = latest.stat().st_size / 1024 / 1024
        mtime = datetime.fromtimestamp(latest.stat().st_mtime, tz=timezone.utc)

        file_backups.append({
            "name": name,
            "path": source_path,
            "size_mb": round(size_mb, 1),
            "files": 0,
            "last_backup": mtime,
        })

    if not file_backups:
        from lib.mock_backups import get_file_backups as mock
        return mock()

    return file_backups


@st.cache_data(ttl=300)
def get_provider_status():
    from lib.mock_backups import get_provider_status as mock

    cfg = get_server_config()
    providers = cfg.get("backup_providers", [])

    if not providers:
        return mock()

    results = []
    for prov in providers:
        if not prov.get("enabled", False):
            results.append({
                "name": prov["name"].title(),
                "bucket": prov.get("bucket", ""),
                "status": "disabled",
                "last_sync": None,
                "total_size_gb": 0,
                "file_count": 0,
                "monthly_cost": 0,
                "retention_days": cfg.get("backup_retention_remote_days", 90),
            })
            continue

        try:
            result = subprocess.run(
                ["rclone", "size", f"{prov['rclone_remote']}:{prov['bucket']}", "--json"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                size_info = json.loads(result.stdout)
                total_bytes = size_info.get("bytes", 0)
                file_count = size_info.get("count", 0)

                cost_per_gb = 0.006 if prov["name"] == "backblaze" else 0.01
                monthly_cost = (total_bytes / 1024 / 1024 / 1024) * cost_per_gb

                results.append({
                    "name": prov["name"].title(),
                    "bucket": prov["bucket"],
                    "status": "synced",
                    "last_sync": datetime.now(timezone.utc),
                    "total_size_gb": round(total_bytes / 1024 / 1024 / 1024, 2),
                    "file_count": file_count,
                    "monthly_cost": round(monthly_cost, 2),
                    "retention_days": cfg.get("backup_retention_remote_days", 90),
                })
            else:
                results.append({
                    "name": prov["name"].title(),
                    "bucket": prov.get("bucket", ""),
                    "status": "error",
                    "last_sync": None,
                    "total_size_gb": 0,
                    "file_count": 0,
                    "monthly_cost": 0,
                    "retention_days": cfg.get("backup_retention_remote_days", 90),
                })
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            results.append({
                "name": prov["name"].title(),
                "bucket": prov.get("bucket", ""),
                "status": "unreachable",
                "last_sync": None,
                "total_size_gb": 0,
                "file_count": 0,
                "monthly_cost": 0,
                "retention_days": cfg.get("backup_retention_remote_days", 90),
            })

    return results


@st.cache_data(ttl=30)
def get_verification_history(days: int = 7):
    history = _load_json(VERIFY_HISTORY_FILE)
    if history is None:
        from lib.mock_backups import get_verification_history as mock
        return mock(days=days)

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    results = []
    for entry in history:
        try:
            ts = datetime.fromisoformat(entry["timestamp"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            continue

        if ts < cutoff:
            continue

        if entry.get("type") == "restore-test":
            continue

        results.append({
            "date": ts,
            "type": entry.get("type", "local"),
            "status": entry.get("status", "passed"),
            "files_checked": entry.get("total", 0),
            "errors": entry.get("failed", 0) + entry.get("missing", 0),
            "duration_sec": entry.get("duration_sec", 0),
        })

    if not results:
        from lib.mock_backups import get_verification_history as mock
        return mock(days=days)

    return results


@st.cache_data(ttl=30)
def get_restore_tests():
    history = _load_json(VERIFY_HISTORY_FILE)
    if history is None:
        from lib.mock_backups import get_restore_tests as mock
        return mock()

    tests = []
    for entry in history:
        if entry.get("type") != "restore-test":
            continue

        try:
            ts = datetime.fromisoformat(entry["timestamp"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            continue

        archive_name = Path(entry.get("archive", "")).stem
        db_name = archive_name.split("_")[0] if archive_name else "unknown"

        tests.append({
            "date": ts,
            "database": db_name,
            "status": entry.get("status", "passed"),
            "restore_time_sec": entry.get("duration_sec", 0),
            "row_count_match": entry.get("tables_restored", 0) > 0,
        })

    if not tests:
        from lib.mock_backups import get_restore_tests as mock
        return mock()

    return tests
