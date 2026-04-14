"""
Read site and server data from the Ansible inventory.

In production (on the VPS), reads directly from the inventory YAML file.
In local dev, reads from a local copy if available, otherwise falls back to mock data.
"""

import os
from pathlib import Path

import streamlit as st
import yaml


INVENTORY_PATH_SERVER = "/opt/ansible-omwom/inventories/production/hosts.yml"
INVENTORY_PATH_LOCAL = os.environ.get("INVENTORY_PATH", "")


def _find_inventory() -> Path | None:
    if INVENTORY_PATH_LOCAL:
        p = Path(INVENTORY_PATH_LOCAL)
        if p.exists():
            return p

    server = Path(INVENTORY_PATH_SERVER)
    if server.exists():
        return server

    return None


@st.cache_data(ttl=60)
def _load_inventory() -> dict | None:
    path = _find_inventory()
    if path is None:
        return None

    with open(path, "r") as f:
        data = yaml.safe_load(f)

    return data.get("all", {}).get("vars", {})


def inventory_available() -> bool:
    return _load_inventory() is not None


def _read_wp_version(site_name: str) -> str:
    """Read WP version from the site's wp-includes/version.php file."""
    import re
    version_file = Path(f"/var/www/{site_name}/public/wp-includes/version.php")
    if not version_file.exists():
        return "—"
    try:
        content = version_file.read_text(errors="replace")
        match = re.search(r"\$wp_version\s*=\s*['\"]([^'\"]+)['\"]", content)
        if match:
            return match.group(1)
    except (OSError, PermissionError):
        pass
    return "—"


@st.cache_data(ttl=300)
def get_wordpress_sites() -> list[dict]:
    inv = _load_inventory()
    if inv is None:
        from lib.mock_data import get_wordpress_sites as mock
        return mock()

    sites = inv.get("wordpress_sites") or []
    return [
        {
            "name": s.get("name", ""),
            "domain": s.get("domain", ""),
            "php_version": s.get("php_version", "8.3"),
            "status": "running",
            "db_name": s.get("db_name", f"{s.get('name', '')}_db"),
            "wp_version": _read_wp_version(s.get("name", "")),
        }
        for s in sites
    ]


def get_odoo_instances() -> list[dict]:
    inv = _load_inventory()
    if inv is None:
        from lib.mock_data import get_odoo_instances as mock
        return mock()

    instances = inv.get("odoo_instances") or []
    return [
        {
            "name": i.get("name", ""),
            "domain": i.get("domain", ""),
            "port": i.get("port", 8069),
            "status": "running",
            "db_name": i.get("db_name", f"{i.get('name', '')}_db"),
            "version": inv.get("odoo_version", "17.0"),
        }
        for i in instances
    ]


def get_mail_domains() -> list[dict]:
    inv = _load_inventory()
    if inv is None:
        from lib.mock_data import get_mail_domains as mock
        return mock()

    domains = inv.get("mail_domains") or []
    return [
        {
            "domain": d.get("domain", "") if isinstance(d, dict) else d,
            "mailboxes": 0,
            "accounts": [],
        }
        for d in domains
    ]


def get_management_subdomains() -> list[dict]:
    inv = _load_inventory()
    if inv is None:
        return []

    return inv.get("management_subdomains") or []


def get_server_config() -> dict:
    inv = _load_inventory()
    if inv is None:
        return {}

    return {
        "primary_domain": inv.get("primary_domain", ""),
        "admin_email": inv.get("admin_email", ""),
        "server_hostname": inv.get("server_hostname", ""),
        "odoo_version": inv.get("odoo_version", ""),
        "odoo_python_version": inv.get("odoo_python_version", ""),
        "backup_retention_local_days": inv.get("backup_retention_local_days", 7),
        "backup_retention_remote_days": inv.get("backup_retention_remote_days", 90),
        "backup_providers": inv.get("backup_providers", []),
    }
