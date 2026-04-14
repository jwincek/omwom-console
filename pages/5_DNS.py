import streamlit as st
import pandas as pd

from lib.dns_checker import check_domain, check_a_record
from lib.inventory import (
    get_wordpress_sites,
    get_odoo_instances,
    get_mail_domains,
    get_management_subdomains,
    get_server_config,
)
from lib.database import log_activity

st.set_page_config(page_title="DNS - OMWOM Console", page_icon=":satellite:", layout="wide")

st.title("DNS Checker")
st.caption("Verify DNS records for managed domains")

STATUS_ICONS = {"ok": "🟢", "warning": "🟠", "error": "🔴", "missing": "⚪"}

# ── Configuration ───────────────────────────────────────
with st.expander("Server settings", expanded=False):
    st.caption("These values are used to validate DNS records against your server.")
    cfg_col1, cfg_col2 = st.columns(2)
    expected_ip = cfg_col1.text_input(
        "Server IP",
        value="",
        placeholder="e.g. 198.51.100.42",
        help="A records should point to this IP. Leave blank to skip IP validation.",
        key="dns_expected_ip",
    )
    mail_server = cfg_col2.text_input(
        "Mail server hostname",
        value="mail.omwom.com",
        help="MX records should point here.",
        key="dns_mail_server",
    )

# ── Quick check ─────────────────────────────────────────
st.subheader("Check a Domain")

check_col1, check_col2 = st.columns([3, 1])
custom_domain = check_col1.text_input(
    "Domain to check",
    placeholder="example.com",
    label_visibility="collapsed",
    key="dns_custom_domain",
)

if check_col2.button("Check DNS", type="primary") and custom_domain:
    log_activity("dns", "domain_checked", custom_domain)

    with st.spinner(f"Checking DNS for {custom_domain}..."):
        checks = check_domain(custom_domain, expected_ip=expected_ip, mail_server=mail_server)

    st.session_state._dns_custom_result = {
        "domain": custom_domain,
        "checks": checks,
    }

if "_dns_custom_result" in st.session_state:
    result = st.session_state._dns_custom_result
    domain = result["domain"]
    checks = result["checks"]

    ok_count = sum(1 for c in checks if c.status == "ok")
    total = len(checks)
    overall = "🟢" if ok_count == total else ("🟠" if ok_count >= 3 else "🔴")

    st.markdown(f"### {overall} {domain} — {ok_count}/{total} checks passed")

    for check in checks:
        icon = STATUS_ICONS.get(check.status, "⚪")
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 2, 3])
            c1.markdown(f"{icon} **{check.record_type}**")
            c2.code(check.actual, language=None)
            if check.detail:
                c3.caption(check.detail)
            elif check.status == "ok":
                c3.caption("Configured correctly")

st.divider()

# ── Bulk check all managed domains ──────────────────────
st.subheader("All Managed Domains")
st.caption("Check DNS for the primary domain, all management subdomains, WordPress sites, Odoo instances, and mail domains.")

include_mgmt = st.checkbox("Include omwom.com management subdomains", value=True, key="dns_include_mgmt")

if st.button("Check all domains"):
    domains = set()

    server_cfg = get_server_config()
    primary = server_cfg.get("primary_domain", "")

    if include_mgmt and primary:
        domains.add(primary)
        for sub in get_management_subdomains():
            sub_name = sub.get("sub", "")
            if sub_name:
                domains.add(f"{sub_name}.{primary}")

    for site in get_wordpress_sites():
        if site.get("domain"):
            domains.add(site["domain"])
    for inst in get_odoo_instances():
        if inst.get("domain"):
            domains.add(inst["domain"])
    for md in get_mail_domains():
        if md.get("domain"):
            domains.add(md["domain"])

    log_activity("dns", "bulk_check", f"{len(domains)} domains")

    all_results = {}
    progress = st.progress(0, text="Checking domains...")

    for i, domain in enumerate(sorted(domains)):
        progress.progress((i + 1) / len(domains), text=f"Checking {domain}...")
        checks = check_domain(domain, expected_ip=expected_ip, mail_server=mail_server)
        all_results[domain] = checks

    progress.empty()
    st.session_state._dns_bulk_results = all_results

if "_dns_bulk_results" in st.session_state:
    all_results = st.session_state._dns_bulk_results

    summary_data = []
    for domain, checks in sorted(all_results.items()):
        row = {"Domain": domain}
        for check in checks:
            icon = STATUS_ICONS.get(check.status, "⚪")
            row[check.record_type] = f"{icon} {check.status}"
        ok_count = sum(1 for c in checks if c.status == "ok")
        row["Score"] = f"{ok_count}/{len(checks)}"
        summary_data.append(row)

    summary_df = pd.DataFrame(summary_data)

    def highlight_score(row):
        score = row.get("Score", "")
        if score.startswith("5/"):
            return [""] * len(row)
        elif score.startswith(("4/", "3/")):
            return ["background-color: #fef3c7"] * len(row)
        else:
            return ["background-color: #fee2e2"] * len(row)

    st.dataframe(
        summary_df.style.apply(highlight_score, axis=1),
        width="stretch",
        hide_index=True,
    )

    # Detail expanders for each domain
    for domain, checks in sorted(all_results.items()):
        ok_count = sum(1 for c in checks if c.status == "ok")
        total = len(checks)
        overall = STATUS_ICONS["ok"] if ok_count == total else (
            STATUS_ICONS["warning"] if ok_count >= 3 else STATUS_ICONS["error"]
        )

        with st.expander(f"{overall} {domain} — {ok_count}/{total}"):
            for check in checks:
                icon = STATUS_ICONS.get(check.status, "⚪")
                col1, col2, col3 = st.columns([1, 3, 3])
                col1.markdown(f"{icon} **{check.record_type}**")
                col2.code(check.actual, language=None)
                col3.caption(check.detail if check.detail else "OK")

# ── Reference ───────────────────────────────────────────
st.divider()
with st.expander("Required DNS records for a new domain"):
    st.markdown(
        "When adding a new domain to the server, these records need to be configured "
        "at the domain's DNS provider:\n\n"
        "| Record | Name | Value | Purpose |\n"
        "|--------|------|-------|---------|\n"
        "| **A** | `@` | Server IP | Points domain to VPS |\n"
        "| **A** | `www` | Server IP | Points www subdomain to VPS |\n"
        "| **MX** | `@` | `mail.omwom.com` (pri 10) | Routes email to mail server |\n"
        "| **TXT** | `@` | `v=spf1 mx a:mail.omwom.com ~all` | SPF authorization |\n"
        "| **TXT** | `default._domainkey` | *(from Modoboa)* | DKIM signing key |\n"
        "| **TXT** | `_dmarc` | `v=DMARC1; p=quarantine; ...` | DMARC policy |\n"
    )
    st.caption(
        "The DKIM key is generated per-domain inside Modoboa. "
        "After adding the domain via `mail-add-domain.yml`, retrieve the key from "
        "the Modoboa admin panel at mail.omwom.com."
    )
