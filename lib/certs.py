"""
Read SSL certificate data from /var/log/ssl-report.json
(written by cert_monitor.py daily at 6:00 AM).

Falls back to mock data when the file isn't available.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st


SSL_REPORT = Path("/var/log/ssl-report.json")


def real_data_available() -> bool:
    return SSL_REPORT.exists()


@st.cache_data(ttl=60)
def get_ssl_certificates():
    if not SSL_REPORT.exists():
        from lib.mock_data import get_ssl_certificates as mock
        return mock()

    try:
        with open(SSL_REPORT, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        from lib.mock_data import get_ssl_certificates as mock
        return mock()

    certs = data.get("certificates", [])
    if not certs:
        from lib.mock_data import get_ssl_certificates as mock
        return mock()

    results = []
    status_map = {"OK": "ok", "WARNING": "warning", "CRITICAL": "critical", "ERROR": "error"}

    for c in certs:
        if c.get("status") == "ERROR":
            results.append({
                "domain": c["domain"],
                "expiry": datetime.now(timezone.utc),
                "status": "error",
                "error": c.get("error", "Unknown error"),
            })
            continue

        try:
            expiry = datetime.fromisoformat(c["expiry"])
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            continue

        results.append({
            "domain": c["domain"],
            "expiry": expiry,
            "status": status_map.get(c.get("status", "OK"), "ok"),
            "issuer": c.get("issuer", ""),
        })

    return results


@st.cache_data(ttl=60)
def get_report_metadata():
    if not SSL_REPORT.exists():
        return None

    try:
        with open(SSL_REPORT, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    try:
        ts = datetime.fromisoformat(data["timestamp"])
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    except (KeyError, ValueError):
        ts = None

    return {
        "timestamp": ts,
        "checked": data.get("checked", 0),
        "ok": data.get("ok", 0),
        "warning": data.get("warning", 0),
        "critical": data.get("critical", 0),
        "error": data.get("error", 0),
    }
