"""
Mock data for the backup status page.

In production, this data comes from:
- /var/log/backup.log (backup_manager.py output)
- /var/log/backup-verify.log (backup_verify.py output)
- /var/backups/checksums.json (integrity data)
- rclone lsl output (remote provider status)
"""

from datetime import datetime, timedelta, timezone


def get_backup_history(days: int = 14):
    now = datetime.now(timezone.utc)
    history = []
    for i in range(days):
        day = now - timedelta(days=i)
        run_time = day.replace(hour=2, minute=0, second=3)
        is_today = i == 0

        status = "success"
        error_detail = ""
        if i == 5:
            status = "partial"
            error_detail = "File backup of /var/vmail/ timed out after 600s. Database backups completed. Remote upload skipped for mail_data.tar.gz."
        if i == 11:
            status = "failed"
            error_detail = "PostgreSQL connection refused — postgresql.service was stopped for maintenance. MariaDB backups completed (3/3). PostgreSQL backups failed (0/5)."

        history.append({
            "date": run_time,
            "status": status,
            "databases": 8 if status != "failed" else 3,
            "files": 5 if status == "success" else (3 if status == "partial" else 0),
            "size_mb": 2847 + (i * 12) - (i * i),
            "duration_sec": 340 + (i * 5) + (120 if status == "partial" else 0),
            "in_progress": is_today and now.hour < 3,
            "error_detail": error_detail,
        })
    return history


def get_database_backups():
    now = datetime.now(timezone.utc)
    last_run = now.replace(hour=2, minute=0, second=3)
    if now.hour < 2:
        last_run -= timedelta(days=1)

    return [
        {"database": "slowbread_db", "type": "mariadb", "size_mb": 245,
         "last_backup": last_run, "checksum_ok": True},
        {"database": "wp2_db", "type": "mariadb", "size_mb": 89,
         "last_backup": last_run, "checksum_ok": True},
        {"database": "wp3_db", "type": "mariadb", "size_mb": 34,
         "last_backup": last_run, "checksum_ok": True},
        {"database": "odoo1_db", "type": "postgresql", "size_mb": 512,
         "last_backup": last_run, "checksum_ok": True},
        {"database": "odoo2_db", "type": "postgresql", "size_mb": 387,
         "last_backup": last_run, "checksum_ok": True},
        {"database": "semaphore", "type": "postgresql", "size_mb": 28,
         "last_backup": last_run, "checksum_ok": True},
        {"database": "modoboa", "type": "postgresql", "size_mb": 156,
         "last_backup": last_run, "checksum_ok": True},
        {"database": "oilregion_db", "type": "postgresql", "size_mb": 67,
         "last_backup": last_run, "checksum_ok": True},
    ]


def get_file_backups():
    now = datetime.now(timezone.utc)
    last_run = now.replace(hour=2, minute=15, second=0)
    if now.hour < 2:
        last_run -= timedelta(days=1)

    return [
        {"name": "WordPress sites", "path": "/var/www/",
         "size_mb": 892, "files": 12450, "last_backup": last_run},
        {"name": "Odoo data", "path": "/opt/odoo/data/",
         "size_mb": 634, "files": 3200, "last_backup": last_run},
        {"name": "Odoo addons", "path": "/opt/odoo/custom-addons/",
         "size_mb": 45, "files": 890, "last_backup": last_run},
        {"name": "Mail data", "path": "/var/vmail/",
         "size_mb": 1240, "files": 45600, "last_backup": last_run},
        {"name": "Nginx configs", "path": "/etc/nginx/",
         "size_mb": 1, "files": 24, "last_backup": last_run - timedelta(days=3)},
    ]


def get_provider_status():
    now = datetime.now(timezone.utc)
    return [
        {
            "name": "Backblaze B2",
            "bucket": "omwom-backups",
            "status": "synced",
            "last_sync": now - timedelta(hours=5, minutes=12),
            "total_size_gb": 18.4,
            "file_count": 342,
            "monthly_cost": 0.11,
            "retention_days": 90,
        },
        {
            "name": "Hetzner Storage Box",
            "bucket": "u12345.your-storagebox.de",
            "status": "synced",
            "last_sync": now - timedelta(hours=5, minutes=8),
            "total_size_gb": 18.4,
            "file_count": 342,
            "monthly_cost": 3.81,
            "retention_days": 90,
        },
    ]


def get_verification_history(days: int = 7):
    now = datetime.now(timezone.utc)
    history = []
    for i in range(days):
        day = now - timedelta(days=i)
        history.append({
            "date": day.replace(hour=5, minute=0, second=12),
            "type": "local" if day.weekday() != 6 else "remote",
            "status": "passed",
            "files_checked": 342 if day.weekday() != 6 else 342,
            "errors": 0,
            "duration_sec": 45 if day.weekday() != 6 else 180,
        })
    history[3]["status"] = "warning"
    history[3]["errors"] = 1
    return history


def get_restore_tests():
    now = datetime.now(timezone.utc)
    return [
        {
            "date": (now - timedelta(days=11)).replace(hour=7, minute=0),
            "database": "wp2_db",
            "status": "passed",
            "restore_time_sec": 23,
            "row_count_match": True,
        },
        {
            "date": (now - timedelta(days=41)).replace(hour=7, minute=0),
            "database": "odoo1_db",
            "status": "passed",
            "restore_time_sec": 67,
            "row_count_match": True,
        },
    ]
