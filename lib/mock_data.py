"""
Mock data that simulates what the real server would return.

When connected to the real server, these functions get replaced by
calls to Semaphore API, inventory_manager.py, health scripts, etc.
"""

from datetime import datetime, timedelta, timezone


def get_services():
    return [
        {"name": "Nginx", "status": "running", "type": "core"},
        {"name": "MariaDB", "status": "running", "type": "core"},
        {"name": "PostgreSQL", "status": "running", "type": "core"},
        {"name": "Postfix", "status": "running", "type": "mail"},
        {"name": "Dovecot", "status": "running", "type": "mail"},
        {"name": "PHP 8.3 FPM", "status": "running", "type": "core"},
        {"name": "Semaphore", "status": "running", "type": "management"},
        {"name": "Uptime Kuma", "status": "running", "type": "monitoring"},
        {"name": "Portainer", "status": "running", "type": "monitoring"},
    ]


def get_wordpress_sites():
    return [
        {
            "name": "slowbread",
            "domain": "slowbirdbread.com",
            "php_version": "8.3",
            "status": "running",
            "db_name": "slowbread_db",
            "wp_version": "6.9.4",
        },
        {
            "name": "wp2",
            "domain": "clientsite2.com",
            "php_version": "8.3",
            "status": "running",
            "db_name": "wp2_db",
            "wp_version": "6.9.4",
        },
        {
            "name": "wp3",
            "domain": "clientsite3.com",
            "php_version": "8.3",
            "status": "stopped",
            "db_name": "wp3_db",
            "wp_version": "6.8.1",
        },
    ]


def get_odoo_instances():
    return [
        {
            "name": "odoo1",
            "domain": "odoo1.example.com",
            "port": 8069,
            "status": "running",
            "db_name": "odoo1_db",
            "version": "17.0",
        },
        {
            "name": "odoo2",
            "domain": "odoo2.example.com",
            "port": 8070,
            "status": "running",
            "db_name": "odoo2_db",
            "version": "17.0",
        },
    ]


def get_mail_domains():
    return [
        {
            "domain": "omwom.com",
            "mailboxes": 3,
            "accounts": [
                {"address": "admin@omwom.com", "name": "Admin"},
                {"address": "noreply@omwom.com", "name": "No Reply"},
                {"address": "postmaster@omwom.com", "name": "Postmaster"},
            ],
        },
        {
            "domain": "slowbirdbread.com",
            "mailboxes": 2,
            "accounts": [
                {"address": "admin@slowbirdbread.com", "name": "Admin"},
                {"address": "info@slowbirdbread.com", "name": "Info"},
            ],
        },
        {
            "domain": "clientsite2.com",
            "mailboxes": 1,
            "accounts": [
                {"address": "contact@clientsite2.com", "name": "Contact"},
            ],
        },
    ]


def get_ssl_certificates():
    now = datetime.now(timezone.utc)
    return [
        {"domain": "omwom.com", "expiry": now + timedelta(days=62), "status": "ok"},
        {"domain": "mail.omwom.com", "expiry": now + timedelta(days=62), "status": "ok"},
        {"domain": "ops.omwom.com", "expiry": now + timedelta(days=62), "status": "ok"},
        {"domain": "status.omwom.com", "expiry": now + timedelta(days=62), "status": "ok"},
        {"domain": "slowbirdbread.com", "expiry": now + timedelta(days=12), "status": "warning"},
        {"domain": "clientsite2.com", "expiry": now + timedelta(days=45), "status": "ok"},
        {"domain": "clientsite3.com", "expiry": now + timedelta(days=5), "status": "critical"},
        {"domain": "odoo1.example.com", "expiry": now + timedelta(days=30), "status": "ok"},
        {"domain": "odoo2.example.com", "expiry": now + timedelta(days=30), "status": "ok"},
    ]


def get_backup_status():
    now = datetime.now(timezone.utc)
    return {
        "last_run": now - timedelta(hours=8, minutes=15),
        "status": "success",
        "next_run": now + timedelta(hours=15, minutes=45),
        "databases_backed_up": 8,
        "files_backed_up": 5,
        "total_size_mb": 2847,
        "providers": [
            {"name": "Backblaze B2", "status": "synced", "last_sync": now - timedelta(hours=5)},
            {"name": "Hetzner", "status": "synced", "last_sync": now - timedelta(hours=5)},
        ],
        "last_verify": now - timedelta(days=1, hours=3),
        "verify_status": "passed",
    }


def get_server_stats():
    return {
        "uptime_days": 47,
        "cpu_usage_percent": 23,
        "ram_used_gb": 8.8,
        "ram_total_gb": 12.0,
        "disk_used_gb": 77,
        "disk_total_gb": 240,
        "load_average": "1.24, 0.98, 0.87",
    }
