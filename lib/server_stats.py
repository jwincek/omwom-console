"""
Live server metrics and service status.

Uses psutil for CPU/RAM/disk/uptime and systemctl for service states.
Falls back to mock data when running in non-Linux environments (local dev).
"""

import subprocess
import sys
from datetime import datetime, timezone

import streamlit as st


try:
    import psutil
    _psutil_available = True
except ImportError:
    _psutil_available = False


def _is_linux_server() -> bool:
    return sys.platform.startswith("linux") and _psutil_available


def real_data_available() -> bool:
    return _is_linux_server()


@st.cache_data(ttl=15)
def get_server_stats() -> dict:
    if not _is_linux_server():
        from lib.mock_data import get_server_stats as mock
        return mock()

    uptime_seconds = datetime.now(timezone.utc).timestamp() - psutil.boot_time()
    uptime_days = int(uptime_seconds // 86400)

    cpu_percent = psutil.cpu_percent(interval=None)

    mem = psutil.virtual_memory()
    ram_used_gb = (mem.total - mem.available) / 1024 / 1024 / 1024
    ram_total_gb = mem.total / 1024 / 1024 / 1024

    disk = psutil.disk_usage("/")
    disk_used_gb = disk.used / 1024 / 1024 / 1024
    disk_total_gb = disk.total / 1024 / 1024 / 1024

    load1, load5, load15 = psutil.getloadavg()

    return {
        "uptime_days": uptime_days,
        "uptime_seconds": uptime_seconds,
        "cpu_usage_percent": round(cpu_percent),
        "ram_used_gb": round(ram_used_gb, 1),
        "ram_total_gb": round(ram_total_gb, 1),
        "ram_percent": round(mem.percent),
        "disk_used_gb": round(disk_used_gb),
        "disk_total_gb": round(disk_total_gb),
        "disk_percent": round(disk.percent),
        "load_average": f"{load1:.2f}, {load5:.2f}, {load15:.2f}",
        "load_1m": load1,
    }


# Service list organized by category — matches dashboard presentation
CORE_SERVICES = [
    {"name": "Nginx", "unit": "nginx", "type": "core"},
    {"name": "MariaDB", "unit": "mariadb", "type": "core"},
    {"name": "PostgreSQL", "unit": "postgresql", "type": "core"},
    {"name": "Postfix", "unit": "postfix", "type": "mail"},
    {"name": "Dovecot", "unit": "dovecot", "type": "mail"},
    {"name": "PHP 8.3 FPM", "unit": "php8.3-fpm", "type": "core"},
    {"name": "Semaphore", "unit": "semaphore", "type": "management"},
    {"name": "Fail2ban", "unit": "fail2ban", "type": "security"},
]


def _systemctl_is_active(unit: str) -> str:
    try:
        result = subprocess.run(
            ["systemctl", "is-active", unit],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() or "unknown"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "unknown"


@st.cache_data(ttl=30)
def get_services() -> list[dict]:
    if not _is_linux_server():
        from lib.mock_data import get_services as mock
        return mock()

    results = []
    for svc in CORE_SERVICES:
        state = _systemctl_is_active(svc["unit"])
        results.append({
            "name": svc["name"],
            "unit": svc["unit"],
            "type": svc["type"],
            "status": "running" if state == "active" else state,
        })
    return results
