import streamlit as st
import pandas as pd
from datetime import datetime, timezone

from lib.database import get_recent_activity
from lib.semaphore import get_client
from lib.inventory import (
    get_wordpress_sites,
    get_odoo_instances,
    get_mail_domains,
    inventory_available,
)
from lib.backups import get_backup_status, real_data_available as backups_real
from lib.certs import get_ssl_certificates, get_report_metadata as cert_report_meta, real_data_available as certs_real
from lib.mock_data import (
    get_server_stats,
    get_services,
)

st.set_page_config(
    page_title="OMWOM Console",
    page_icon=":satellite:",
    layout="wide",
)

client = get_client()

st.title("OMWOM Console")
data_warnings = []
if client.mock_mode:
    data_warnings.append("Semaphore: mock")
if not inventory_available():
    data_warnings.append("Inventory: mock")
if not backups_real():
    data_warnings.append("Backups: mock")
if not certs_real():
    data_warnings.append("SSL: mock")

if data_warnings:
    st.caption("Server overview and management dashboard — 🟠 " + " · ".join(data_warnings))
else:
    st.caption("Server overview and management dashboard")

# ── Gather data ─────────────────────────────────────────
stats = get_server_stats()
services = get_services()
wp_sites = get_wordpress_sites()
odoo_instances = get_odoo_instances()
mail_domains = get_mail_domains()
certs = get_ssl_certificates()
backup = get_backup_status()

# ── Alerts ──────────────────────────────────────────────
alerts = []

for cert in certs:
    if cert.get("status") == "error":
        alerts.append(("error", f"SSL check failed for **{cert['domain']}**: {cert.get('error', 'unknown error')} — [Check DNS](/DNS)"))
        continue
    days_left = (cert["expiry"] - datetime.now(timezone.utc)).days
    if days_left <= 7:
        alerts.append(("error", f"SSL certificate for **{cert['domain']}** expires in {days_left} days — [Check DNS](/DNS)"))
    elif days_left <= 14:
        alerts.append(("warning", f"SSL certificate for **{cert['domain']}** expires in {days_left} days — [Check DNS](/DNS)"))

hours_since_backup = (datetime.now(timezone.utc) - backup["last_run"]).total_seconds() / 3600
if backup["status"] != "success":
    alerts.append(("error", f"Last backup **{backup['status']}** ({hours_since_backup:.0f}h ago) — [View Backups](/Backups)"))
elif hours_since_backup > 26:
    alerts.append(("warning", f"Last backup was {hours_since_backup:.0f} hours ago — [View Backups](/Backups)"))

if backup["verify_status"] != "passed":
    alerts.append(("error", f"Backup verification **{backup['verify_status']}** — [View Backups](/Backups)"))

down_services = [s for s in services if s["status"] != "running"]
for svc in down_services:
    alerts.append(("error", f"Service **{svc['name']}** is {svc['status']} — [Run Health Check](/Health)"))

down_wp = [s for s in wp_sites if s["status"] != "running"]
for site in down_wp:
    alerts.append(("warning", f"WordPress site **{site['domain']}** is {site['status']} — [Manage Sites](/Sites)"))

down_odoo = [i for i in odoo_instances if i["status"] != "running"]
for inst in down_odoo:
    alerts.append(("warning", f"Odoo instance **{inst['domain']}** is {inst['status']} — [Manage Sites](/Sites)"))

if alerts:
    error_alerts = [a for a in alerts if a[0] == "error"]
    warning_alerts = [a for a in alerts if a[0] == "warning"]

    with st.container(border=True):
        st.markdown(f"### ⚠ {len(alerts)} alert{'s' if len(alerts) != 1 else ''}")
        for level, msg in error_alerts:
            st.error(msg)
        for level, msg in warning_alerts:
            st.warning(msg)

    st.divider()

# ── Server metrics ──────────────────────────────────────
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Uptime", f"{stats['uptime_days']}d")
col2.metric("CPU", f"{stats['cpu_usage_percent']}%")
col3.metric(
    "RAM",
    f"{stats['ram_used_gb']:.1f} GB",
    delta=f"{stats['ram_total_gb'] - stats['ram_used_gb']:.1f} GB free",
    delta_color="off",
)
col4.metric(
    "Disk",
    f"{stats['disk_used_gb']} GB",
    delta=f"{stats['disk_total_gb'] - stats['disk_used_gb']} GB free",
    delta_color="off",
)
col5.metric("Load", stats["load_average"].split(",")[0].strip())

st.divider()

# ── Sites overview ──────────────────────────────────────
left, right = st.columns(2)

with left:
    st.markdown("### [WordPress Sites](/Sites)")
    for site in wp_sites:
        status_icon = "🟢" if site["status"] == "running" else "🔴"
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 2, 1])
            c1.markdown(f"[**{site['domain']}**](https://{site['domain']})")
            c2.caption(f"PHP {site['php_version']} / WP {site['wp_version']}")
            c3.markdown(f"{status_icon} [{site['status']}](https://{site['domain']}/wp-admin)")

    st.markdown("### [Odoo Instances](/Sites)")
    for inst in odoo_instances:
        status_icon = "🟢" if inst["status"] == "running" else "🔴"
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 2, 1])
            c1.markdown(f"[**{inst['domain']}**](https://{inst['domain']})")
            c2.caption(f"Odoo {inst['version']} / port {inst['port']}")
            c3.markdown(f"{status_icon} {inst['status']}")

with right:
    st.markdown("### [Mail Domains](/Sites)")
    for domain in mail_domains:
        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            c1.markdown(f"[**{domain['domain']}**](https://mail.omwom.com/#/domains/)")
            c2.caption(f"{domain['mailboxes']} mailboxes")

    st.markdown("### [Backup Status](/Backups)")
    backup_icon = {"success": "🟢", "partial": "🟠", "failed": "🔴"}.get(backup["status"], "⚪")
    verify_icon = "🟢" if backup["verify_status"] == "passed" else ("⚪" if backup["verify_status"] == "unknown" else "🟠")

    with st.container(border=True):
        b1, b2 = st.columns(2)
        b1.metric("Last Backup", f"{hours_since_backup:.0f}h ago")
        b2.metric("Sites", backup["databases_backed_up"])

        verify_label = backup["verify_status"]
        if verify_label == "unknown":
            verify_label = "pending"

        st.caption(
            f"{backup_icon} Last run: **{backup['status']}** · "
            f"{verify_icon} Last verify: **{verify_label}** · "
            f"Size: {backup['total_size_mb']:,.0f} MB"
        )

        prov_status_icons = {"synced": "🟢", "disabled": "⚪", "error": "🔴", "unreachable": "🟠"}
        for provider in backup["providers"]:
            prov_icon = prov_status_icons.get(provider["status"], "🟠")
            if provider["last_sync"]:
                prov_hours = (datetime.now(timezone.utc) - provider["last_sync"]).total_seconds() / 3600
                st.caption(f"{prov_icon} {provider['name']}: {provider['status']} ({prov_hours:.0f}h ago)")
            else:
                st.caption(f"{prov_icon} {provider['name']}: {provider['status']}")

st.divider()

# ── SSL certificates ───────────────────────────────────
st.markdown("### [SSL Certificates](/DNS)")

cert_meta = cert_report_meta()
if cert_meta and cert_meta.get("timestamp"):
    hours_since = (datetime.now(timezone.utc) - cert_meta["timestamp"]).total_seconds() / 3600
    st.caption(
        f"Last checked {hours_since:.0f}h ago · "
        f"{cert_meta['ok']} OK · {cert_meta['warning']} warning · "
        f"{cert_meta['critical']} critical · {cert_meta['error']} error"
    )
elif certs_real():
    st.caption("Daily check via cert_monitor.py at 6:00 AM")

cert_data = []
for cert in certs:
    days_left = (cert["expiry"] - datetime.now(timezone.utc)).days
    cert_data.append({
        "Domain": cert["domain"],
        "Expires": cert["expiry"].strftime("%Y-%m-%d"),
        "Days Left": days_left,
        "Status": cert["status"].upper(),
    })

cert_df = pd.DataFrame(cert_data)


def highlight_cert_status(row):
    if row["Status"] == "CRITICAL":
        return ["background-color: #fee2e2"] * len(row)
    elif row["Status"] == "WARNING":
        return ["background-color: #fef3c7"] * len(row)
    elif row["Status"] == "ERROR":
        return ["background-color: #fed7aa"] * len(row)
    return [""] * len(row)


st.dataframe(
    cert_df.style.apply(highlight_cert_status, axis=1),
    width="stretch",
    hide_index=True,
)

st.divider()

# ── Core services ───────────────────────────────────────
st.markdown("### [Core Services](/Health)")

svc_cols = st.columns(len(services))
for i, svc in enumerate(services):
    icon = "🟢" if svc["status"] == "running" else "🔴"
    svc_cols[i].markdown(f"{icon}\n\n**{svc['name']}**")

st.divider()

# ── Activity log ────────────────────────────────────────
st.subheader("Recent Activity")

activity = get_recent_activity()
if activity:
    activity_df = pd.DataFrame(activity)
    activity_df["timestamp"] = pd.to_datetime(activity_df["timestamp"]).dt.strftime(
        "%Y-%m-%d %H:%M"
    )
    st.dataframe(activity_df, width="stretch", hide_index=True)
else:
    st.info("No activity recorded yet. Actions you take in the console will appear here.")

# ── Sidebar ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### OMWOM Console")
    st.markdown("[Semaphore](https://ops.omwom.com) · [Mail](https://mail.omwom.com) · [Status](https://status.omwom.com)")
    st.caption("[Portainer](https://docker.omwom.com) · [Server](https://omwom.com)")

    st.divider()

    wp_running = sum(1 for s in wp_sites if s["status"] == "running")
    odoo_running = sum(1 for s in odoo_instances if s["status"] == "running")
    svc_running = sum(1 for s in services if s["status"] == "running")
    certs_ok = sum(1 for c in certs if c["status"] == "ok")

    st.markdown(f"[**{wp_running}/{len(wp_sites)}** WordPress sites up](/Sites)")
    st.markdown(f"[**{odoo_running}/{len(odoo_instances)}** Odoo instances up](/Sites)")
    st.markdown(f"[**{len(mail_domains)}** mail domains](/Sites)")
    st.markdown(f"[**{svc_running}/{len(services)}** core services up](/Health)")
    st.markdown(f"[**{certs_ok}/{len(certs)}** SSL certs OK](/DNS)")

    if alerts:
        st.divider()
        st.markdown(f"**{len(alerts)}** alerts")
