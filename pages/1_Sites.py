import re
import streamlit as st

from lib.database import log_activity
from lib.semaphore import get_client
from lib.mock_data import get_wordpress_sites, get_odoo_instances, get_mail_domains

st.set_page_config(page_title="Sites - OMWOM Console", page_icon=":satellite:", layout="wide")

st.title("Managed Sites")
st.caption("WordPress sites, Odoo instances, and mail domains on the server")

client = get_client()

if client.mock_mode:
    st.caption("🟠 Running in mock mode — Semaphore not connected")

PHP_VERSIONS = ["8.2", "8.3"]

# ── Data ────────────────────────────────────────────────
wp_sites = get_wordpress_sites()
odoo_instances = get_odoo_instances()
mail_domains = get_mail_domains()

# Build a lookup: domain → mail accounts
mail_by_domain = {
    md["domain"]: md.get("accounts", [])
    for md in mail_domains
}

tab_wp, tab_odoo, tab_mail = st.tabs([
    f"WordPress ({len(wp_sites)})",
    f"Odoo ({len(odoo_instances)})",
    f"Mail ({len(mail_domains)})",
])

# ── WordPress tab ───────────────────────────────────────
with tab_wp:
    for site in wp_sites:
        status_icon = "🟢" if site["status"] == "running" else "🔴"
        with st.expander(f"{status_icon} **{site['domain']}** ({site['name']})", expanded=False):
            info_col, actions_col = st.columns([3, 2])

            with info_col:
                st.markdown(f"**Site ID:** `{site['name']}`")
                st.markdown(f"**Domain:** {site['domain']}")
                st.markdown(f"**WP Version:** {site['wp_version']}")
                st.markdown(f"**Database:** `{site['db_name']}`")
                st.caption(f"Path: `/var/www/{site['name']}/public`")
                st.markdown(f"[Open site →](https://{site['domain']}) · [WP Admin →](https://{site['domain']}/wp-admin)")

                site_mail = mail_by_domain.get(site["domain"], [])
                if site_mail:
                    st.markdown(f"**Email** ({len(site_mail)} accounts)")
                    for acct in site_mail:
                        st.caption(f"📧 `{acct['address']}` — {acct['name']}")
                else:
                    st.caption("📧 No email accounts — [Add domain in Modoboa](https://mail.omwom.com/#/domains/)")

            with actions_col:
                # ── Start / Stop ────────────────────────
                is_running = site["status"] == "running"
                toggle_label = "Stop site" if is_running else "Start site"
                toggle_action = "disable" if is_running else "enable"

                if st.button(
                    toggle_label,
                    key=f"toggle_wp_{site['name']}",
                    type="secondary" if is_running else "primary",
                ):
                    log_activity(
                        "wordpress",
                        f"site_{toggle_action}d",
                        f"{toggle_action.title()}d {site['name']} ({site['domain']})",
                    )
                    if client.mock_mode:
                        st.info(
                            f"Mock: would trigger `wordpress-toggle.yml` "
                            f"with `wp_action={toggle_action}`"
                        )
                    else:
                        client.run_task(template_id=10, extra_vars={
                            "wp_name": site["name"],
                            "wp_domain": site["domain"],
                            "wp_php": site["php_version"],
                            "wp_action": toggle_action,
                        })
                        st.success(f"Site {toggle_action}d")

                # ── PHP version change ──────────────────
                current_php_idx = PHP_VERSIONS.index(site["php_version"]) if site["php_version"] in PHP_VERSIONS else 0
                other_versions = [v for v in PHP_VERSIONS if v != site["php_version"]]

                if other_versions:
                    new_php = st.selectbox(
                        f"PHP version (current: {site['php_version']})",
                        [site["php_version"]] + other_versions,
                        key=f"php_{site['name']}",
                    )

                    if new_php != site["php_version"]:
                        if st.button(
                            f"Switch to PHP {new_php}",
                            key=f"php_change_{site['name']}",
                            type="primary",
                        ):
                            log_activity(
                                "wordpress",
                                "php_changed",
                                f"{site['name']}: PHP {site['php_version']} → {new_php}",
                            )
                            if client.mock_mode:
                                st.success(
                                    f"Mock: would trigger `wordpress-php-change.yml` "
                                    f"({site['php_version']} → {new_php})"
                                )
                            else:
                                client.run_task(template_id=9, extra_vars={
                                    "wp_name": site["name"],
                                    "wp_domain": site["domain"],
                                    "wp_php_old": site["php_version"],
                                    "wp_php_new": new_php,
                                })
                                st.success(f"PHP version change triggered ({site['php_version']} → {new_php})")

            # ── Remove ──────────────────────────────────
            st.divider()
            if st.button(f"Remove {site['name']}", key=f"remove_wp_{site['name']}", type="secondary"):
                st.session_state[f"_confirm_remove_wp_{site['name']}"] = True

            if st.session_state.get(f"_confirm_remove_wp_{site['name']}"):
                st.warning(
                    f"This will remove **{site['domain']}** ({site['name']}), "
                    f"including its database, files, Nginx config, SSL cert, and PHP-FPM pool. "
                    f"A backup will be created before removal."
                )
                cc1, cc2 = st.columns(2)
                if cc1.button(
                    f"Confirm removal", key=f"confirm_wp_{site['name']}", type="primary"
                ):
                    log_activity("wordpress", "site_removed",
                                 f"Removed {site['name']} ({site['domain']})")
                    if client.mock_mode:
                        st.info("Mock: would trigger `wordpress-remove.yml`")
                    else:
                        client.run_task(template_id=2, extra_vars={
                            "wp_name": site["name"],
                            "wp_domain": site["domain"],
                            "confirm_delete": "YES",
                        })
                        st.success(f"Removal triggered for {site['name']}")
                    st.session_state.pop(f"_confirm_remove_wp_{site['name']}", None)

                if cc2.button("Cancel", key=f"cancel_wp_{site['name']}"):
                    st.session_state.pop(f"_confirm_remove_wp_{site['name']}", None)
                    st.rerun()

    st.divider()

    # ── Add WordPress site ──────────────────────────────
    with st.expander("➕ Add WordPress Site"):
        wp_name = st.text_input(
            "Site identifier", max_chars=16, placeholder="newsite",
            help="Lowercase alphanumeric, 2-16 chars.", key="add_wp_name",
        )
        wp_domain = st.text_input(
            "Domain", placeholder="newsite.com", key="add_wp_domain",
        )
        wp_php = st.selectbox("PHP version", PHP_VERSIONS, index=1, key="add_wp_php")

        name_valid = bool(wp_name and re.match(r"^[a-z][a-z0-9_]{1,15}$", wp_name))
        domain_valid = bool(
            wp_domain and re.match(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z]{2,})+$", wp_domain)
        )
        name_taken = any(s["name"] == wp_name for s in wp_sites)

        if wp_name and name_taken:
            st.warning(f"Site identifier `{wp_name}` is already in use.")
        if wp_name and not name_valid:
            st.warning("Must be 2-16 lowercase alphanumeric characters, starting with a letter.")

        can_add = name_valid and domain_valid and not name_taken

        if st.button("Add WordPress site", type="primary", disabled=not can_add, key="btn_add_wp"):
            log_activity("wordpress", "site_added", f"Added {wp_name} ({wp_domain})")
            if client.mock_mode:
                st.success(
                    f"Mock: would trigger `wordpress-add.yml` with "
                    f"`wp_name={wp_name}`, `wp_domain={wp_domain}`, `wp_php={wp_php}`"
                )
            else:
                task = client.run_task(template_id=1, extra_vars={
                    "wp_name": wp_name, "wp_domain": wp_domain, "wp_php": wp_php,
                })
                st.success(f"WordPress site creation triggered (task #{task['id']})")

# ── Odoo tab ────────────────────────────────────────────
with tab_odoo:
    for inst in odoo_instances:
        status_icon = "🟢" if inst["status"] == "running" else "🔴"
        with st.expander(f"{status_icon} **{inst['domain']}** ({inst['name']})", expanded=False):
            info_col, actions_col = st.columns([3, 2])

            with info_col:
                st.markdown(f"**Instance ID:** `{inst['name']}`")
                st.markdown(f"**Domain:** {inst['domain']}")
                st.markdown(f"**Odoo:** {inst['version']}")
                st.markdown(f"**Port:** {inst['port']}")
                st.markdown(f"**Database:** `{inst['db_name']}`")
                st.caption(f"Config: `/etc/odoo/{inst['name']}.conf`")
                st.markdown(f"[Open site →](https://{inst['domain']}) · [Odoo Admin →](https://{inst['domain']}/web#action=base_setup.action_general_configuration)")

                inst_mail = mail_by_domain.get(inst["domain"], [])
                if inst_mail:
                    st.markdown(f"**Email** ({len(inst_mail)} accounts)")
                    for acct in inst_mail:
                        st.caption(f"📧 `{acct['address']}` — {acct['name']}")
                else:
                    st.caption("📧 No email accounts — [Add domain in Modoboa](https://mail.omwom.com/#/domains/)")

            with actions_col:
                # ── Start / Stop ────────────────────────
                is_running = inst["status"] == "running"
                toggle_label = "Stop instance" if is_running else "Start instance"
                toggle_action = "stop" if is_running else "start"

                if st.button(
                    toggle_label,
                    key=f"toggle_odoo_{inst['name']}",
                    type="secondary" if is_running else "primary",
                ):
                    log_activity(
                        "odoo",
                        f"instance_{toggle_action}ped" if toggle_action == "stop" else "instance_started",
                        f"{toggle_action.title()} {inst['name']} ({inst['domain']})",
                    )
                    if client.mock_mode:
                        st.info(
                            f"Mock: would run `systemctl {toggle_action} {inst['name']}` "
                            f"via Semaphore"
                        )
                    else:
                        client.run_task(template_id=11, extra_vars={
                            "odoo_name": inst["name"],
                            "odoo_action": toggle_action,
                        })
                        st.success(f"Instance {toggle_action} triggered")

            # ── Remove ──────────────────────────────────
            st.divider()
            if st.button(f"Remove {inst['name']}", key=f"remove_odoo_{inst['name']}", type="secondary"):
                st.session_state[f"_confirm_remove_odoo_{inst['name']}"] = True

            if st.session_state.get(f"_confirm_remove_odoo_{inst['name']}"):
                st.warning(
                    f"This will remove **{inst['domain']}** ({inst['name']}), "
                    f"including its database, config, systemd service, and Nginx vhost. "
                    f"A database dump will be created before removal."
                )
                cc1, cc2 = st.columns(2)
                if cc1.button(
                    f"Confirm removal", key=f"confirm_odoo_{inst['name']}", type="primary"
                ):
                    log_activity("odoo", "instance_removed",
                                 f"Removed {inst['name']} ({inst['domain']})")
                    if client.mock_mode:
                        st.info("Mock: would trigger `odoo-remove.yml`")
                    else:
                        client.run_task(template_id=4, extra_vars={
                            "odoo_name": inst["name"],
                            "odoo_domain": inst["domain"],
                            "confirm_delete": "YES",
                        })
                        st.success(f"Removal triggered for {inst['name']}")
                    st.session_state.pop(f"_confirm_remove_odoo_{inst['name']}", None)

                if cc2.button("Cancel", key=f"cancel_odoo_{inst['name']}"):
                    st.session_state.pop(f"_confirm_remove_odoo_{inst['name']}", None)
                    st.rerun()

    st.divider()

    # ── Add Odoo instance ───────────────────────────────
    with st.expander("➕ Add Odoo Instance"):
        odoo_name = st.text_input(
            "Instance identifier", max_chars=16, placeholder="odoo4",
            help="Lowercase alphanumeric, 2-16 chars.", key="add_odoo_name",
        )
        odoo_domain = st.text_input(
            "Domain", placeholder="odoo4.example.com", key="add_odoo_domain",
        )

        o_name_valid = bool(odoo_name and re.match(r"^[a-z][a-z0-9_]{1,15}$", odoo_name))
        o_domain_valid = bool(
            odoo_domain and re.match(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z]{2,})+$", odoo_domain)
        )
        o_name_taken = any(i["name"] == odoo_name for i in odoo_instances)

        if odoo_name and o_name_taken:
            st.warning(f"Instance identifier `{odoo_name}` is already in use.")

        can_add_odoo = o_name_valid and o_domain_valid and not o_name_taken

        if st.button("Add Odoo instance", type="primary", disabled=not can_add_odoo, key="btn_add_odoo"):
            log_activity("odoo", "instance_added", f"Added {odoo_name} ({odoo_domain})")
            if client.mock_mode:
                st.success(
                    f"Mock: would trigger `odoo-add.yml` with "
                    f"`odoo_name={odoo_name}`, `odoo_domain={odoo_domain}`"
                )
                st.caption("Ports will be auto-assigned by the playbook.")
            else:
                task = client.run_task(template_id=3, extra_vars={
                    "odoo_name": odoo_name, "odoo_domain": odoo_domain,
                })
                st.success(f"Odoo instance creation triggered (task #{task['id']})")

# ── Mail tab ────────────────────────────────────────────
with tab_mail:
    for domain in mail_domains:
        with st.expander(f"**{domain['domain']}** — {domain['mailboxes']} mailboxes", expanded=False):
            st.markdown(f"**Domain:** {domain['domain']}")
            st.markdown(f"**Mailboxes:** {domain['mailboxes']}")
            st.markdown("[Open in Modoboa →](https://mail.omwom.com/#/domains/)", unsafe_allow_html=False)

            if st.button(f"Remove {domain['domain']}", key=f"remove_mail_{domain['domain']}", type="secondary"):
                st.session_state[f"_confirm_remove_mail_{domain['domain']}"] = True

            if st.session_state.get(f"_confirm_remove_mail_{domain['domain']}"):
                st.warning(
                    f"This will remove **{domain['domain']}** from Modoboa, "
                    f"including all mailboxes and mail data. "
                    f"Mail data will be archived before removal."
                )
                mc1, mc2 = st.columns(2)
                if mc1.button(
                    f"Confirm removal",
                    key=f"confirm_mail_{domain['domain']}", type="primary",
                ):
                    log_activity("mail", "domain_removed", f"Removed {domain['domain']}")
                    if client.mock_mode:
                        st.info("Mock: would trigger `mail-remove-domain.yml`")
                    else:
                        client.run_task(template_id=6, extra_vars={
                            "mail_domain": domain["domain"],
                            "confirm_delete": "YES",
                        })
                        st.success(f"Removal triggered for {domain['domain']}")
                    st.session_state.pop(f"_confirm_remove_mail_{domain['domain']}", None)

                if mc2.button("Cancel", key=f"cancel_mail_{domain['domain']}"):
                    st.session_state.pop(f"_confirm_remove_mail_{domain['domain']}", None)
                    st.rerun()

    st.divider()

    # ── Add mail domain ─────────────────────────────────
    with st.expander("➕ Add Mail Domain"):
        mail_domain = st.text_input(
            "Domain", placeholder="newclient.com", key="add_mail_domain",
        )

        m_domain_valid = bool(
            mail_domain and re.match(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z]{2,})+$", mail_domain)
        )
        m_domain_taken = any(d["domain"] == mail_domain for d in mail_domains)

        if mail_domain and m_domain_taken:
            st.warning(f"Domain `{mail_domain}` is already configured.")

        can_add_mail = m_domain_valid and not m_domain_taken

        if st.button("Add mail domain", type="primary", disabled=not can_add_mail, key="btn_add_mail"):
            log_activity("mail", "domain_added", f"Added {mail_domain}")
            if client.mock_mode:
                st.success(f"Mock: would trigger `mail-add-domain.yml` with `mail_domain={mail_domain}`")
                st.info(
                    f"After adding, configure DNS records for {mail_domain}:\n"
                    f"- MX → mail.omwom.com (priority 10)\n"
                    f"- TXT (SPF) → v=spf1 mx a:mail.omwom.com ~all\n"
                    f"- TXT (DMARC) → v=DMARC1; p=quarantine\n"
                    f"- TXT (DKIM) → get from Modoboa admin panel\n\n"
                    f"Then create mailboxes at mail.omwom.com."
                )
            else:
                task = client.run_task(template_id=5, extra_vars={
                    "mail_domain": mail_domain,
                })
                st.success(f"Mail domain addition triggered (task #{task['id']})")
