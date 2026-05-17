import re
import secrets
import string
import streamlit as st

from lib.database import log_activity
from lib.semaphore import get_client
from lib.modoboa import get_modoboa_client
from lib.inventory import get_wordpress_sites, get_odoo_instances, get_oilregion_hubs, get_mail_domains, inventory_available

st.set_page_config(page_title="Sites - OMWOM Console", page_icon=":satellite:", layout="wide")

st.title("Managed Sites")
st.caption("WordPress sites, Odoo instances, and mail domains on the server")

client = get_client()
modoboa = get_modoboa_client()

if client.mock_mode:
    st.caption("🟠 Semaphore: mock mode")
if modoboa.mock_mode:
    st.caption("🟠 Modoboa: mock mode")
if not inventory_available():
    st.caption("🟠 Inventory: mock data")


def generate_password(length=24):
    chars = string.ascii_letters + string.digits + "!@#$%&*"
    return "".join(secrets.choice(chars) for _ in range(length))

PHP_VERSIONS = ["8.2", "8.3"]

# ── Read query params for deep-linking from Dashboard ───
qp_tab = st.query_params.get("tab", "")
qp_site = st.query_params.get("site", "")
qp_domain = st.query_params.get("domain", "")

# ── Data ────────────────────────────────────────────────
wp_sites = get_wordpress_sites()
odoo_instances = get_odoo_instances()
oilregion_hubs = get_oilregion_hubs()
mail_domains = get_mail_domains()

# Build a lookup: domain → mail accounts
mail_by_domain = {}
for md in mail_domains:
    accts = modoboa.list_accounts(md["domain"])
    mail_by_domain[md["domain"]] = [
        {"address": a.get("username", a.get("mailbox", {}).get("full_address", "")),
         "name": a.get("first_name", "")}
        for a in accts
    ]

tab_wp, tab_odoo, tab_hub, tab_mail = st.tabs([
    f"WordPress ({len(wp_sites)})",
    f"Odoo ({len(odoo_instances)})",
    f"Hub ({len(oilregion_hubs)})",
    f"Mail ({len(mail_domains)})",
])

# ── WordPress tab ───────────────────────────────────────
with tab_wp:
    for site in wp_sites:
        status_icon = "🟢" if site["status"] == "running" else "🔴"
        is_focus = qp_tab == "wordpress" and qp_site == site["name"]
        with st.expander(f"{status_icon} **{site['domain']}** ({site['name']})", expanded=is_focus):
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
                        client.run_playbook("wordpress-toggle.yml", extra_vars={
                            "wp_name": site["name"],
                            "wp_domain": site["domain"],
                            "wp_php": site["php_version"],
                            "wp_action": toggle_action,
                        })
                        st.success(f"Site {toggle_action}d")

                # ── Quick backup ────────────────────────
                if st.button(
                    f"Backup {site['db_name']}",
                    key=f"backup_wp_{site['name']}",
                ):
                    log_activity("backup", "backup_triggered",
                                 f"Quick backup: {site['db_name']} ({site['domain']})")
                    if client.mock_mode:
                        st.success(f"Mock: would backup `{site['db_name']}` (local, no upload)")
                    else:
                        client.run_playbook("backup-run.yml", extra_vars={
                            "backup_scope": "single",
                            "backup_database": site["db_name"],
                            "backup_skip_upload": True,
                        })
                        st.success(f"Backup of `{site['db_name']}` triggered")

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
                                client.run_playbook("wordpress-php-change.yml", extra_vars={
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
                        st.session_state.pop(f"_confirm_remove_wp_{site['name']}", None)
                    else:
                        with st.status(f"Removing {site['name']}...", expanded=True) as status:
                            task = client.run_playbook("wordpress-remove.yml", extra_vars={
                                "wp_name": site["name"],
                                "wp_domain": site["domain"],
                                "confirm_delete": "YES",
                            })
                            st.write(f"Semaphore task #{task['id']} started")
                            result = client.wait_for_task(task["id"], timeout=300)
                            if result["status"] == "success":
                                status.update(label=f"{site['name']} removed", state="complete")
                            else:
                                status.update(label=f"Removal failed: {result['status']}", state="error")

                        st.session_state.pop(f"_confirm_remove_wp_{site['name']}", None)
                        get_wordpress_sites.clear()
                        st.rerun()

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

        st.markdown("**Email setup** (optional)")
        add_mail = st.checkbox(
            "Also create mail domain",
            value=True,
            key="add_wp_mail_domain",
            help=f"Adds the domain to Modoboa so it can receive email.",
        )
        add_default_mailboxes = st.checkbox(
            "Create default mailboxes (postmaster, info)",
            value=True,
            key="add_wp_default_mailboxes",
            disabled=not add_mail,
            help="Creates postmaster@ and info@ accounts via the Modoboa API.",
        )

        can_add = name_valid and domain_valid and not name_taken

        if st.button("Add WordPress site", type="primary", disabled=not can_add, key="btn_add_wp"):
            log_activity("wordpress", "site_added", f"Added {wp_name} ({wp_domain})")

            # Step 1: WordPress
            if client.mock_mode:
                st.success(
                    f"Mock: would trigger `wordpress-add.yml` with "
                    f"`wp_name={wp_name}`, `wp_domain={wp_domain}`, `wp_php={wp_php}`"
                )
            else:
                task = client.run_playbook("wordpress-add.yml", extra_vars={
                    "wp_name": wp_name, "wp_domain": wp_domain, "wp_php": wp_php,
                })
                st.success(f"WordPress site creation triggered (task #{task['id']})")

            # Step 2: Mail domain (if enabled)
            if add_mail:
                log_activity("mail", "domain_added", f"Auto-added {wp_domain} with WordPress site")
                if client.mock_mode:
                    st.info(f"Mock: would trigger `mail-add-domain.yml` for `{wp_domain}`")
                else:
                    mail_task = client.run_playbook("mail-add-domain.yml", extra_vars={
                        "mail_domain": wp_domain,
                    })
                    st.success(f"Mail domain addition triggered (task #{mail_task['id']})")

                # Step 3: Default mailboxes (if enabled)
                if add_default_mailboxes:
                    default_pass = generate_password()
                    log_activity("mail", "default_mailboxes_created", f"postmaster@{wp_domain}, info@{wp_domain}")

                    if modoboa.mock_mode:
                        st.info(f"Mock: would create `postmaster@{wp_domain}` and `info@{wp_domain}`")
                    else:
                        try:
                            modoboa.create_default_accounts(wp_domain, default_pass)
                            st.success(f"Default mailboxes created for {wp_domain}")
                            with st.container(border=True):
                                st.markdown(f"**Default mailbox credentials for `{wp_domain}`**")
                                st.code(
                                    f"postmaster@{wp_domain}  /  {default_pass}\n"
                                    f"info@{wp_domain}        /  {default_pass}",
                                    language="text",
                                )
                                st.caption("Save these credentials. Change them after first login.")
                        except Exception as e:
                            st.warning(
                                f"Mailbox creation via Modoboa API failed: {e}. "
                                f"Create them manually at [mail.omwom.com](https://mail.omwom.com/)."
                            )

# ── Odoo tab ────────────────────────────────────────────
with tab_odoo:
    for inst in odoo_instances:
        status_icon = "🟢" if inst["status"] == "running" else "🔴"
        is_focus = qp_tab == "odoo" and qp_site == inst["name"]
        with st.expander(f"{status_icon} **{inst['domain']}** ({inst['name']})", expanded=is_focus):
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
                        client.run_playbook("odoo-toggle.yml", extra_vars={
                            "odoo_name": inst["name"],
                            "odoo_action": toggle_action,
                        })
                        st.success(f"Instance {toggle_action} triggered")

                # ── Quick backup ────────────────────────
                if st.button(
                    f"Backup {inst['db_name']}",
                    key=f"backup_odoo_{inst['name']}",
                ):
                    log_activity("backup", "backup_triggered",
                                 f"Quick backup: {inst['db_name']} ({inst['domain']})")
                    if client.mock_mode:
                        st.success(f"Mock: would backup `{inst['db_name']}` (local, no upload)")
                    else:
                        client.run_playbook("backup-run.yml", extra_vars={
                            "backup_scope": "single",
                            "backup_database": inst["db_name"],
                            "backup_skip_upload": True,
                        })
                        st.success(f"Backup of `{inst['db_name']}` triggered")

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
                        st.session_state.pop(f"_confirm_remove_odoo_{inst['name']}", None)
                    else:
                        with st.status(f"Removing {inst['name']}...", expanded=True) as status:
                            task = client.run_playbook("odoo-remove.yml", extra_vars={
                                "odoo_name": inst["name"],
                                "odoo_domain": inst["domain"],
                                "confirm_delete": "YES",
                            })
                            st.write(f"Semaphore task #{task['id']} started")
                            result = client.wait_for_task(task["id"], timeout=300)
                            if result["status"] == "success":
                                status.update(label=f"{inst['name']} removed", state="complete")
                            else:
                                status.update(label=f"Removal failed: {result['status']}", state="error")

                        st.session_state.pop(f"_confirm_remove_odoo_{inst['name']}", None)
                        get_odoo_instances.clear()
                        st.rerun()

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

        st.markdown("**Email setup** (optional)")
        add_odoo_mail = st.checkbox(
            "Also create mail domain",
            value=True,
            key="add_odoo_mail_domain",
        )
        add_odoo_default_mailboxes = st.checkbox(
            "Create default mailboxes (postmaster, info)",
            value=True,
            key="add_odoo_default_mailboxes",
            disabled=not add_odoo_mail,
        )

        can_add_odoo = o_name_valid and o_domain_valid and not o_name_taken

        if st.button("Add Odoo instance", type="primary", disabled=not can_add_odoo, key="btn_add_odoo"):
            log_activity("odoo", "instance_added", f"Added {odoo_name} ({odoo_domain})")

            # Step 1: Odoo
            if client.mock_mode:
                st.success(
                    f"Mock: would trigger `odoo-add.yml` with "
                    f"`odoo_name={odoo_name}`, `odoo_domain={odoo_domain}`"
                )
                st.caption("Ports will be auto-assigned by the playbook.")
            else:
                task = client.run_playbook("odoo-add.yml", extra_vars={
                    "odoo_name": odoo_name, "odoo_domain": odoo_domain,
                })
                st.success(f"Odoo instance creation triggered (task #{task['id']})")

            # Step 2: Mail domain (if enabled)
            if add_odoo_mail:
                log_activity("mail", "domain_added", f"Auto-added {odoo_domain} with Odoo instance")
                if client.mock_mode:
                    st.info(f"Mock: would trigger `mail-add-domain.yml` for `{odoo_domain}`")
                else:
                    mail_task = client.run_playbook("mail-add-domain.yml", extra_vars={
                        "mail_domain": odoo_domain,
                    })
                    st.success(f"Mail domain addition triggered (task #{mail_task['id']})")

                # Step 3: Default mailboxes (if enabled)
                if add_odoo_default_mailboxes:
                    default_pass = generate_password()
                    log_activity("mail", "default_mailboxes_created", f"postmaster@{odoo_domain}, info@{odoo_domain}")

                    if modoboa.mock_mode:
                        st.info(f"Mock: would create `postmaster@{odoo_domain}` and `info@{odoo_domain}`")
                    else:
                        try:
                            modoboa.create_default_accounts(odoo_domain, default_pass)
                            st.success(f"Default mailboxes created for {odoo_domain}")
                            with st.container(border=True):
                                st.markdown(f"**Default mailbox credentials for `{odoo_domain}`**")
                                st.code(
                                    f"postmaster@{odoo_domain}  /  {default_pass}\n"
                                    f"info@{odoo_domain}        /  {default_pass}",
                                    language="text",
                                )
                                st.caption("Save these credentials. Change them after first login.")
                        except Exception as e:
                            st.warning(
                                f"Mailbox creation via Modoboa API failed: {e}. "
                                f"Create them manually at [mail.omwom.com](https://mail.omwom.com/)."
                            )

# ── Hub tab ─────────────────────────────────────────────
with tab_hub:
    for hub in oilregion_hubs:
        status_icon = "🟢" if hub["status"] == "running" else "🔴"
        is_focus = qp_tab == "hub" and qp_site == hub["name"]
        with st.expander(f"{status_icon} **{hub['domain']}** ({hub['name']})", expanded=is_focus):
            info_col, actions_col = st.columns([3, 2])

            with info_col:
                st.markdown(f"**Hub ID:** `{hub['name']}`")
                st.markdown(f"**Domain:** {hub['domain']}")
                st.markdown(f"**Python:** {hub['python_version']}")
                st.markdown(f"**Port:** {hub['port']} (gunicorn, 127.0.0.1)")
                st.markdown(f"**Database:** `{hub['db_name']}`")
                if hub.get("repo_branch"):
                    st.caption(
                        f"Branch: `{hub['repo_branch']}` · App: `/var/www/{hub['name']}/app`"
                    )
                else:
                    st.caption(f"App: `/var/www/{hub['name']}/app`")
                st.markdown(
                    f"[Open site →](https://{hub['domain']}) · "
                    f"[Wagtail →](https://{hub['domain']}/cms/) · "
                    f"[Admin dashboard →](https://{hub['domain']}/dashboard/)"
                )

                hub_mail = mail_by_domain.get(hub["domain"], [])
                if hub_mail:
                    st.markdown(f"**Email** ({len(hub_mail)} accounts)")
                    for acct in hub_mail:
                        st.caption(f"📧 `{acct['address']}` — {acct['name']}")
                else:
                    st.caption("📧 No email accounts — [Add domain in Modoboa](https://mail.omwom.com/#/domains/)")

            with actions_col:
                # ── Start / Stop ────────────────────────
                is_running = hub["status"] == "running"
                toggle_label = "Stop hub" if is_running else "Start hub"
                toggle_action = "stop" if is_running else "start"

                if st.button(
                    toggle_label,
                    key=f"toggle_hub_{hub['name']}",
                    type="secondary" if is_running else "primary",
                ):
                    log_activity(
                        "oilregion",
                        "hub_stopped" if toggle_action == "stop" else "hub_started",
                        f"{toggle_action.title()} {hub['name']} ({hub['domain']})",
                    )
                    if client.mock_mode:
                        st.info(
                            f"Mock: would trigger `oilregion-hub-toggle.yml` "
                            f"with `hub_action={toggle_action}`"
                        )
                    else:
                        client.run_playbook("oilregion-hub-toggle.yml", extra_vars={
                            "hub_name": hub["name"],
                            "hub_action": toggle_action,
                        })
                        st.success(f"Hub {toggle_action} triggered")

                # ── Update (git pull + migrate) ─────────
                if st.button(
                    "Update (git pull + migrate)",
                    key=f"update_hub_{hub['name']}",
                ):
                    log_activity(
                        "oilregion",
                        "hub_updated",
                        f"Update {hub['name']} (pull + migrate + restart)",
                    )
                    if client.mock_mode:
                        st.info(
                            f"Mock: would trigger `oilregion-hub-update.yml` "
                            f"for `{hub['name']}`"
                        )
                    else:
                        client.run_playbook("oilregion-hub-update.yml", extra_vars={
                            "hub_name": hub["name"],
                        })
                        st.success("Update triggered")

                # ── Quick backup ────────────────────────
                if st.button(
                    f"Backup {hub['db_name']}",
                    key=f"backup_hub_{hub['name']}",
                ):
                    log_activity("backup", "backup_triggered",
                                 f"Quick backup: {hub['db_name']} ({hub['domain']})")
                    if client.mock_mode:
                        st.success(f"Mock: would backup `{hub['db_name']}` (local, no upload)")
                    else:
                        client.run_playbook("backup-run.yml", extra_vars={
                            "backup_scope": "single",
                            "backup_database": hub["db_name"],
                            "backup_skip_upload": True,
                        })
                        st.success(f"Backup of `{hub['db_name']}` triggered")

            # ── Remove ──────────────────────────────────
            st.divider()
            if st.button(f"Remove {hub['name']}", key=f"remove_hub_{hub['name']}", type="secondary"):
                st.session_state[f"_confirm_remove_hub_{hub['name']}"] = True

            if st.session_state.get(f"_confirm_remove_hub_{hub['name']}"):
                st.warning(
                    f"This will remove **{hub['domain']}** ({hub['name']}), "
                    f"including its database, app dir, venv, media uploads, systemd services, "
                    f"Nginx vhost, and SSL cert. Pre-deletion archives "
                    f"(DB + media + app) are written to `/var/backups/removed_{hub['name']}_*`."
                )
                cc1, cc2 = st.columns(2)
                if cc1.button(
                    f"Confirm removal", key=f"confirm_hub_{hub['name']}", type="primary"
                ):
                    log_activity("oilregion", "hub_removed",
                                 f"Removed {hub['name']} ({hub['domain']})")
                    if client.mock_mode:
                        st.info("Mock: would trigger `oilregion-hub-remove.yml`")
                        st.session_state.pop(f"_confirm_remove_hub_{hub['name']}", None)
                    else:
                        with st.status(f"Removing {hub['name']}...", expanded=True) as status:
                            task = client.run_playbook("oilregion-hub-remove.yml", extra_vars={
                                "hub_name": hub["name"],
                                "hub_domain": hub["domain"],
                                "confirm_delete": "YES",
                            })
                            st.write(f"Semaphore task #{task['id']} started")
                            result = client.wait_for_task(task["id"], timeout=300)
                            if result["status"] == "success":
                                status.update(label=f"{hub['name']} removed", state="complete")
                            else:
                                status.update(label=f"Removal failed: {result['status']}", state="error")

                        st.session_state.pop(f"_confirm_remove_hub_{hub['name']}", None)
                        get_oilregion_hubs.clear()
                        st.rerun()

                if cc2.button("Cancel", key=f"cancel_hub_{hub['name']}"):
                    st.session_state.pop(f"_confirm_remove_hub_{hub['name']}", None)
                    st.rerun()

    st.divider()

    # ── Add Hub instance ────────────────────────────────
    with st.expander("➕ Add Oil Region Hub"):
        hub_name = st.text_input(
            "Hub identifier", max_chars=32, placeholder="oilhub",
            help="Lowercase letters, digits, hyphens, underscores. 2-32 chars.",
            key="add_hub_name",
        )
        hub_domain = st.text_input(
            "Domain", placeholder="oilregionindie.com", key="add_hub_domain",
        )

        h_name_valid = bool(hub_name and re.match(r"^[a-z][a-z0-9_-]{1,31}$", hub_name))
        h_domain_valid = bool(
            hub_domain and re.match(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z]{2,})+$", hub_domain)
        )
        h_name_taken = any(h["name"] == hub_name for h in oilregion_hubs)

        if hub_name and h_name_taken:
            st.warning(f"Hub identifier `{hub_name}` is already in use.")
        if hub_name and not h_name_valid:
            st.warning(
                "Must be 2-32 lowercase chars (letters, digits, hyphens, underscores), "
                "starting with a letter."
            )

        st.markdown("**Email setup** (recommended — the hub sends transactional email)")
        add_hub_mail = st.checkbox(
            "Also create mail domain",
            value=True,
            key="add_hub_mail_domain",
            help="Adds the domain to Modoboa so the hub can send digests, booking notifications, etc.",
        )
        add_hub_default_mailboxes = st.checkbox(
            "Create default mailboxes (postmaster, info)",
            value=True,
            key="add_hub_default_mailboxes",
            disabled=not add_hub_mail,
        )

        can_add_hub = h_name_valid and h_domain_valid and not h_name_taken

        if st.button("Add Oil Region Hub", type="primary", disabled=not can_add_hub, key="btn_add_hub"):
            log_activity("oilregion", "hub_added", f"Added {hub_name} ({hub_domain})")

            # Step 1: Hub install
            if client.mock_mode:
                st.success(
                    f"Mock: would trigger `oilregion-hub-add.yml` with "
                    f"`hub_name={hub_name}`, `hub_domain={hub_domain}`"
                )
                st.caption("Port and Redis DB will be auto-assigned by the playbook.")
            else:
                task = client.run_playbook("oilregion-hub-add.yml", extra_vars={
                    "hub_name": hub_name, "hub_domain": hub_domain,
                })
                st.success(f"Hub provisioning triggered (task #{task['id']})")
            st.caption(
                f"After provisioning completes, run `createsuperuser` for the first admin user — "
                f"see `/root/.credentials/{hub_name}.txt` on the server."
            )

            # Step 2: Mail domain (if enabled)
            if add_hub_mail:
                log_activity("mail", "domain_added", f"Auto-added {hub_domain} with hub")
                if client.mock_mode:
                    st.info(f"Mock: would trigger `mail-add-domain.yml` for `{hub_domain}`")
                else:
                    mail_task = client.run_playbook("mail-add-domain.yml", extra_vars={
                        "mail_domain": hub_domain,
                    })
                    st.success(f"Mail domain addition triggered (task #{mail_task['id']})")

                if add_hub_default_mailboxes:
                    default_pass = generate_password()
                    log_activity("mail", "default_mailboxes_created",
                                 f"postmaster@{hub_domain}, info@{hub_domain}")

                    if modoboa.mock_mode:
                        st.info(f"Mock: would create `postmaster@{hub_domain}` and `info@{hub_domain}`")
                    else:
                        try:
                            modoboa.create_default_accounts(hub_domain, default_pass)
                            st.success(f"Default mailboxes created for {hub_domain}")
                            with st.container(border=True):
                                st.markdown(f"**Default mailbox credentials for `{hub_domain}`**")
                                st.code(
                                    f"postmaster@{hub_domain}  /  {default_pass}\n"
                                    f"info@{hub_domain}        /  {default_pass}",
                                    language="text",
                                )
                                st.caption("Save these credentials. Change them after first login.")
                        except Exception as e:
                            st.warning(
                                f"Mailbox creation via Modoboa API failed: {e}. "
                                f"Create them manually at [mail.omwom.com](https://mail.omwom.com/)."
                            )

# ── Mail tab ────────────────────────────────────────────
with tab_mail:
    for domain in mail_domains:
        accounts = modoboa.list_accounts(domain["domain"])

        is_focus = qp_tab == "mail" and qp_domain == domain["domain"]
        with st.expander(f"**{domain['domain']}** — {len(accounts)} accounts", expanded=is_focus):
            info_col, actions_col = st.columns([3, 2])

            with info_col:
                st.markdown(f"**Domain:** {domain['domain']}")
                st.markdown(f"[Open in Modoboa →](https://mail.omwom.com/#/domains/)")

                if accounts:
                    st.markdown(f"**Accounts** ({len(accounts)})")
                    for acct in accounts:
                        role_badge = " *(admin)*" if acct.get("role") == "DomainAdmins" else ""
                        active_icon = "🟢" if acct.get("is_active", True) else "🔴"
                        st.caption(
                            f"{active_icon} `{acct.get('username', acct.get('mailbox', {}).get('full_address', ''))}`"
                            f" — {acct.get('first_name', '')}{role_badge}"
                        )
                else:
                    st.caption("No email accounts configured")

            with actions_col:
                # ── Add account ─────────────────────────
                st.markdown("**Add account**")
                new_local = st.text_input(
                    "Address",
                    placeholder="info",
                    key=f"new_acct_local_{domain['domain']}",
                    help=f"Local part — will become name@{domain['domain']}",
                )
                new_name = st.text_input(
                    "Display name",
                    placeholder="Info",
                    key=f"new_acct_name_{domain['domain']}",
                )

                new_email = f"{new_local}@{domain['domain']}" if new_local else ""
                local_valid = bool(new_local and re.match(r"^[a-z][a-z0-9._-]*$", new_local))
                already_exists = any(
                    acct.get("username") == new_email or
                    acct.get("mailbox", {}).get("full_address") == new_email
                    for acct in accounts
                )

                if new_local and not local_valid:
                    st.warning("Must start with a letter. Lowercase, numbers, dots, hyphens allowed.")
                if new_local and already_exists:
                    st.warning(f"`{new_email}` already exists.")

                can_create = local_valid and not already_exists and bool(new_local)

                if st.button(
                    f"Create {new_email}" if new_email else "Create account",
                    type="primary",
                    disabled=not can_create,
                    key=f"btn_create_acct_{domain['domain']}",
                ):
                    password = generate_password()
                    log_activity("mail", "account_created", f"Created {new_email}")

                    if modoboa.mock_mode:
                        st.success(f"Mock: would create `{new_email}`")
                    else:
                        modoboa.create_account(
                            email=new_email,
                            password=password,
                            first_name=new_name or new_local.title(),
                        )
                        st.success(f"Account `{new_email}` created")

                    with st.container(border=True):
                        st.markdown(f"**Credentials for `{new_email}`**")
                        st.code(f"Email:    {new_email}\nPassword: {password}", language="text")
                        st.caption("Save these credentials — the password cannot be retrieved later.")

            # ── Remove domain ───────────────────────────
            st.divider()
            if st.button(f"Remove {domain['domain']}", key=f"remove_mail_{domain['domain']}", type="secondary"):
                st.session_state[f"_confirm_remove_mail_{domain['domain']}"] = True

            if st.session_state.get(f"_confirm_remove_mail_{domain['domain']}"):
                st.warning(
                    f"This will remove **{domain['domain']}** from Modoboa, "
                    f"including all {len(accounts)} accounts and mail data. "
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
                        st.session_state.pop(f"_confirm_remove_mail_{domain['domain']}", None)
                    else:
                        with st.status(f"Removing {domain['domain']}...", expanded=True) as status:
                            task = client.run_playbook("mail-remove-domain.yml", extra_vars={
                                "mail_domain": domain["domain"],
                                "confirm_delete": "YES",
                            })
                            st.write(f"Semaphore task #{task['id']} started")
                            result = client.wait_for_task(task["id"], timeout=300)
                            if result["status"] == "success":
                                status.update(label=f"{domain['domain']} removed", state="complete")
                            else:
                                status.update(label=f"Removal failed: {result['status']}", state="error")

                        st.session_state.pop(f"_confirm_remove_mail_{domain['domain']}", None)
                        get_mail_domains.clear()
                        st.rerun()

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

        create_defaults = st.checkbox(
            "Create default mailboxes (postmaster, info)",
            value=True,
            key="add_mail_create_defaults",
        )

        can_add_mail = m_domain_valid and not m_domain_taken

        if st.button("Add mail domain", type="primary", disabled=not can_add_mail, key="btn_add_mail"):
            log_activity("mail", "domain_added", f"Added {mail_domain}")

            if client.mock_mode:
                st.success(f"Mock: would trigger `mail-add-domain.yml` with `mail_domain={mail_domain}`")
            else:
                task = client.run_playbook("mail-add-domain.yml", extra_vars={
                    "mail_domain": mail_domain,
                })
                st.success(f"Mail domain addition triggered (task #{task['id']})")

            if create_defaults:
                default_pass = generate_password()
                if modoboa.mock_mode:
                    st.info(f"Mock: would create `postmaster@{mail_domain}` and `info@{mail_domain}`")
                else:
                    modoboa.create_default_accounts(mail_domain, default_pass)
                    st.success(f"Default mailboxes created for {mail_domain}")

                with st.container(border=True):
                    st.markdown(f"**Default account credentials for `{mail_domain}`**")
                    st.code(
                        f"postmaster@{mail_domain}  /  {default_pass}\n"
                        f"info@{mail_domain}        /  {default_pass}",
                        language="text",
                    )
                    st.caption("Both accounts share this initial password. Change them after first login.")

            st.info(
                f"Configure DNS records for {mail_domain}:\n"
                f"- MX → mail.omwom.com (priority 10)\n"
                f"- TXT (SPF) → v=spf1 mx a:mail.omwom.com ~all\n"
                f"- TXT (DMARC) → v=DMARC1; p=quarantine\n"
                f"- TXT (DKIM) → get from Modoboa admin panel"
            )
