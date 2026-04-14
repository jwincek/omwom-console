import os
import re
import streamlit as st
from pathlib import Path

from lib.database import log_activity
from lib.softaculous import parse_backup_file
from lib.semaphore import get_client
from lib.inventory import get_wordpress_sites

st.set_page_config(page_title="Restore - OMWOM Console", page_icon=":satellite:")

st.title("WordPress Restore")
st.caption("Restore a WordPress site from backup")

client = get_client()

# ── Step 1: Select backup source ────────────────────────
source_mode = st.radio(
    "Backup source",
    ["Upload Softaculous (< 500 MB)", "Softaculous server path", "Internal backup"],
    horizontal=True,
    key="restore_source_mode",
)

if source_mode == "Upload Softaculous (< 500 MB)":
    uploaded = st.file_uploader(
        "Softaculous backup (.tar.gz)",
        type=["gz"],
        help="Upload a .tar.gz backup from Softaculous WordPress Manager",
    )

    if uploaded:
        if st.session_state.get("_last_upload") != uploaded.name:
            with st.spinner("Parsing backup metadata..."):
                file_bytes = uploaded.getvalue()
                info = parse_backup_file(file_bytes)

            if info is None:
                st.error("Could not parse this file. Is it a Softaculous WordPress Manager backup?")
                st.stop()

            # In production, save the upload to the staging directory so the playbook can read it
            staging_path = None
            if not client.mock_mode:
                staging_dir = Path("/srv/restore-staging")
                try:
                    staging_dir.mkdir(parents=True, exist_ok=True)
                    staging_path = staging_dir / uploaded.name
                    staging_path.write_bytes(file_bytes)
                    staging_path.chmod(0o640)
                except (OSError, PermissionError) as e:
                    st.error(f"Could not save upload to {staging_dir}: {e}")
                    st.stop()

            st.session_state._backup_info = info
            st.session_state._last_upload = uploaded.name
            st.session_state._upload_name = uploaded.name
            st.session_state._upload_size_mb = uploaded.size / 1024 / 1024
            st.session_state._backup_path = str(staging_path) if staging_path else None
            st.session_state.pop("_restore_done", None)

elif source_mode == "Softaculous server path":
    st.caption(
        "For large Softaculous backups, SCP the file to the server first, then enter the path here."
    )
    st.code("scp -P 2222 backup.tar.gz sysadmin@YOUR_VPS_IP:/srv/restore-staging/", language="bash")

    server_path = st.text_input(
        "Path to backup on server",
        placeholder="/srv/restore-staging/bigsite.tar.gz",
        key="restore_server_path",
        help="Absolute path to the .tar.gz file on the VPS.",
    )

    # In local dev, allow local file paths for testing
    local_path = st.text_input(
        "Or local path (dev mode only)",
        placeholder="/Users/you/Downloads/backup.tar.gz",
        key="restore_local_path",
        help="For local development: path to a backup file on this machine.",
    ) if client.mock_mode else None

    parse_path = local_path or server_path if client.mock_mode else server_path

    if parse_path and st.button("Parse backup", key="btn_parse_path"):
        if client.mock_mode and local_path:
            local_file = Path(local_path)
            if not local_file.exists():
                st.error(f"File not found: {local_path}")
                st.stop()
            if not local_file.name.endswith((".tar.gz", ".gz")):
                st.error("File must be a .tar.gz archive")
                st.stop()

            with st.spinner(f"Parsing {local_file.name} ({local_file.stat().st_size / 1024 / 1024:.0f} MB)..."):
                info = parse_backup_file(local_file.read_bytes())

            if info is None:
                st.error("Could not parse this file. Is it a Softaculous WordPress Manager backup?")
                st.stop()

            st.session_state._backup_info = info
            st.session_state._last_upload = local_file.name
            st.session_state._upload_name = local_file.name
            st.session_state._upload_size_mb = local_file.stat().st_size / 1024 / 1024
            st.session_state._backup_path = server_path or local_path
            st.session_state.pop("_restore_done", None)

        elif server_path:
            if not server_path.startswith("/"):
                st.error("Path must be absolute (start with /)")
                st.stop()
            if not server_path.endswith((".tar.gz", ".gz")):
                st.error("File must be a .tar.gz archive")
                st.stop()

            st.session_state._backup_path = server_path
            st.session_state._upload_name = os.path.basename(server_path)

            if client.mock_mode:
                st.info(
                    f"Mock mode: can't read server files. "
                    f"In production, the console would parse metadata from `{server_path}` via Semaphore."
                )
                st.stop()
            else:
                st.info(f"Would parse metadata from `{server_path}` on the server")
                st.stop()

elif source_mode == "Internal backup":
    st.caption("Restore an existing site from a backup created by `backup_manager.py`.")

    wp_sites = get_wordpress_sites()

    if not wp_sites:
        st.warning("No WordPress sites found in inventory.")
        st.stop()

    site_options = {f"{s['name']} ({s['domain']})": s for s in wp_sites}
    selected_label = st.selectbox("Site to restore", list(site_options.keys()), key="internal_site")
    selected_site = site_options[selected_label]

    backup_dir = f"/var/backups/sites/wordpress/{selected_site['name']}"
    backup_dir_path = Path(backup_dir)

    if backup_dir_path.exists():
        archives = sorted(backup_dir_path.glob("*.tar.gz"), reverse=True)
    else:
        archives = []

    if client.mock_mode and not archives:
        st.info(
            f"Mock mode: no local backup files at `{backup_dir}`. "
            f"On the server, this would list available backup archives for **{selected_site['name']}**."
        )

        if st.button("Simulate internal restore", key="btn_mock_internal"):
            log_activity("wordpress", "internal_restore_triggered",
                         f"Simulated restore of {selected_site['name']} from internal backup")

            st.session_state._restore_done = {
                "wp_name": selected_site["name"],
                "wp_domain": selected_site["domain"],
                "wp_php": selected_site.get("php_version", "8.3"),
                "old_domain": selected_site["domain"],
                "site_name": selected_site["name"],
                "file_name": f"{selected_site['name']}_20260413_020003.tar.gz",
                "file_size_mb": 0,
                "backup_path": f"{backup_dir}/{selected_site['name']}_20260413_020003.tar.gz",
                "restore_type": "internal",
            }
            st.rerun()

    elif archives:
        archive_options = {}
        for a in archives[:20]:
            size_mb = a.stat().st_size / 1024 / 1024
            mtime = datetime.fromtimestamp(a.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            label = f"{a.name} ({size_mb:.1f} MB, {mtime})"
            archive_options[label] = a

        from datetime import datetime

        selected_archive_label = st.selectbox(
            f"Available backups ({len(archives)} found)",
            list(archive_options.keys()),
            key="internal_archive",
        )
        selected_archive = archive_options[selected_archive_label]

        new_domain = st.text_input(
            "New domain (leave blank to keep current)",
            placeholder=selected_site["domain"],
            key="internal_new_domain",
        )

        if st.button("Restore from backup", type="primary", key="btn_internal_restore"):
            archive_path = str(selected_archive)
            size_mb = selected_archive.stat().st_size / 1024 / 1024

            extra_vars = {
                "wp_name": selected_site["name"],
                "backup_archive": archive_path,
            }
            if new_domain and new_domain != selected_site["domain"]:
                extra_vars["wp_domain_new"] = new_domain

            log_activity("wordpress", "internal_restore_triggered",
                         f"Restoring {selected_site['name']} from {selected_archive.name}"
                         + (f" with domain change → {new_domain}" if new_domain else ""))

            st.session_state._restore_done = {
                "wp_name": selected_site["name"],
                "wp_domain": new_domain or selected_site["domain"],
                "wp_php": selected_site.get("php_version", "8.3"),
                "old_domain": selected_site["domain"],
                "site_name": selected_site["name"],
                "file_name": selected_archive.name,
                "file_size_mb": size_mb,
                "backup_path": archive_path,
                "restore_type": "internal",
            }
            st.rerun()
    else:
        st.warning(f"No backup archives found at `{backup_dir}`. Run a backup first.")

# ── Show instructions if no backup parsed yet ───────────
if "_backup_info" not in st.session_state and "_restore_done" not in st.session_state:
    st.divider()
    st.markdown("The restore process will:")
    st.markdown(
        "1. **Parse** the backup metadata and show you what's inside\n"
        "2. **Configure** the restore target (site name, domain, PHP version)\n"
        "3. **Validate** your inputs and show a summary\n"
        "4. **Trigger** the restore via Semaphore (runs `wordpress-restore.yml`)\n"
        "5. **Report** the result with credentials and next steps"
    )

    with st.expander("What's in a Softaculous backup?"):
        st.markdown(
            "A Softaculous WordPress Manager backup is a `.tar.gz` archive containing:\n\n"
            "- **Metadata file** — PHP serialized data with the original domain, "
            "database prefix, admin user, and site configuration\n"
            "- **`softsql.sql`** — full database dump\n"
            "- **WordPress files** — core files, themes, plugins, and uploads\n"
            "- **`wp-config.php`** — original configuration (replaced during restore)\n\n"
            "The restore playbook creates a fresh database, imports the SQL dump, "
            "copies the site files, generates a new `wp-config.php` with hardened settings, "
            "and runs `wp search-replace` to update domain references."
        )

    with st.expander("Handling large backups (> 500 MB)"):
        st.markdown(
            "For backups larger than 500 MB, upload the file directly to the server "
            "via SCP instead of through the browser:\n\n"
            "```bash\n"
            "scp -P 2222 largefile.tar.gz sysadmin@YOUR_VPS_IP:/srv/restore-staging/\n"
            "```\n\n"
            "Then select **Server path** mode and enter the path "
            "(e.g., `/srv/restore-staging/largefile.tar.gz`). "
            "The console will parse the metadata on the server and show you the same "
            "confirmation flow. The restore playbook reads from the same path — no file copy needed."
        )
    st.stop()

# ── If restore already done, show results ───────────────
if "_restore_done" in st.session_state:
    p = st.session_state._restore_done

    st.success(f"Restore triggered for **{p['site_name']}**")

    with st.container(border=True):
        s1, s2 = st.columns(2)
        with s1:
            st.markdown("**Source**")
            st.markdown(f"- Domain: `{p['old_domain']}`")
            st.markdown(f"- Site name: {p['site_name']}")
        with s2:
            st.markdown("**Target**")
            st.markdown(f"- Site ID: `{p['wp_name']}`")
            st.markdown(f"- Domain: `{p['wp_domain']}`")
            st.markdown(f"- PHP: {p['wp_php']}")
            st.markdown(f"- Database: `{p['wp_name']}_db`")

    backup_path = p.get("backup_path") or f"/srv/restore-staging/{p['file_name']}"
    is_internal = p.get("restore_type") == "internal"

    with st.status("Restoring WordPress site...", expanded=True) as status:
        size_label = f"{p['file_size_mb']:.1f} MB" if p['file_size_mb'] > 0 else "size unknown"
        st.write(f"📦 Backup: {p['file_name']} ({size_label})")
        domain_msg = "Same domain" if p["old_domain"] == p["wp_domain"] else f"Domain: {p['old_domain']} → {p['wp_domain']}"
        st.write(f"🌐 {domain_msg}")
        st.write(f"🔧 Site ID: {p['wp_name']}, PHP {p['wp_php']}")
        st.write(f"📋 Type: {'Internal backup' if is_internal else 'Softaculous backup'}")
        st.write("")

        if is_internal:
            playbook = "wordpress-restore-internal.yml"
            extra_vars = {
                "wp_name": p["wp_name"],
                "backup_archive": backup_path,
            }
            if p["old_domain"] != p["wp_domain"]:
                extra_vars["wp_domain_new"] = p["wp_domain"]
        else:
            playbook = "wordpress-restore.yml"
            extra_vars = {
                "wp_name": p["wp_name"],
                "wp_domain": p["wp_domain"],
                "wp_php": p["wp_php"],
                "backup_file": backup_path,
            }

        if client.mock_mode:
            st.write(f"Mock: would call Semaphore → `{playbook}`:")
            st.code("\n".join(f"{k}: {v}" for k, v in extra_vars.items()), language="yaml")
            status.update(label="Restore simulated (mock mode)", state="complete")
        else:
            st.write(f"Triggering `{playbook}` via Semaphore:")
            st.code("\n".join(f"{k}: {v}" for k, v in extra_vars.items()), language="yaml")

            task = client.run_playbook(playbook, extra_vars=extra_vars)
            task_id = task["id"]
            st.write(f"Semaphore task #{task_id} started · [View in Semaphore](https://ops.omwom.com/project/1/templates/8)")
            st.caption("This typically takes 1–3 minutes. Progress updates as the playbook runs.")

            progress_placeholder = st.empty()
            last_task_line = ""
            final_status = "unknown"

            for stream_status, new_lines, task_info in client.stream_task(task_id, poll_interval=2.0, timeout=900):
                final_status = stream_status
                for line in new_lines:
                    text = line.get("output", "").strip()
                    if not text:
                        continue
                    if text.startswith("TASK ["):
                        task_name = text.replace("TASK [", "").rstrip(" *]").rstrip("]")
                        last_task_line = task_name
                        progress_placeholder.info(f"🔄 {task_name}")
                    elif text.startswith("PLAY ["):
                        progress_placeholder.info(f"▶ {text}")
                    elif "fatal:" in text.lower() or "error" in text.lower()[:20]:
                        st.error(text)
                    elif text.startswith("PLAY RECAP"):
                        progress_placeholder.info("📊 Play recap")

            if final_status == "success":
                progress_placeholder.empty()
                status.update(label="Restore complete", state="complete")
            else:
                progress_placeholder.empty()
                status.update(label=f"Restore {final_status}", state="error")
                st.error(
                    f"Task #{task_id} ended with status `{final_status}`. "
                    f"Check the [full task output in Semaphore](https://ops.omwom.com/project/1/templates/8) for details."
                )

    # ── Post-restore: add mail domain + default mailboxes ──
    if not client.mock_mode and p.get("add_mail") and p.get("_mail_processed") is not True:
        st.session_state._restore_done["_mail_processed"] = True

        from lib.modoboa import get_modoboa_client
        modoboa = get_modoboa_client()
        mail_domain = p["wp_domain"]

        with st.status(f"Setting up email for {mail_domain}...", expanded=True) as mail_status:
            try:
                mail_task = client.run_playbook("mail-add-domain.yml", extra_vars={
                    "mail_domain": mail_domain,
                })
                mail_result = client.wait_for_task(mail_task["id"], timeout=120)
                if mail_result["status"] == "success":
                    st.write(f"✅ Mail domain `{mail_domain}` added to Modoboa")
                else:
                    st.write(f"⚠ Mail domain playbook ended with status `{mail_result['status']}`")
            except Exception as e:
                st.write(f"⚠ Mail domain addition failed: {e}")

            if p.get("add_mailboxes"):
                from secrets import choice
                from string import ascii_letters, digits
                default_pass = "".join(choice(ascii_letters + digits + "!@#$%&*") for _ in range(24))

                try:
                    if modoboa.mock_mode:
                        st.write(f"Mock: would create `postmaster@{mail_domain}` and `info@{mail_domain}`")
                    else:
                        modoboa.create_default_accounts(mail_domain, default_pass)
                        st.write(f"✅ Default mailboxes created")

                    mail_status.update(label=f"Email ready for {mail_domain}", state="complete")

                    with st.container(border=True):
                        st.markdown(f"**Default mailbox credentials for `{mail_domain}`**")
                        st.code(
                            f"postmaster@{mail_domain}  /  {default_pass}\n"
                            f"info@{mail_domain}        /  {default_pass}",
                            language="text",
                        )
                        st.caption("Save these credentials — change them after first login.")
                        log_activity("mail", "default_mailboxes_created",
                                     f"Created postmaster@{mail_domain}, info@{mail_domain}")
                except Exception as e:
                    mail_status.update(label=f"Mailbox creation failed", state="error")
                    st.warning(
                        f"Mailbox creation via Modoboa API failed: {e}. "
                        f"Create them manually at [mail.omwom.com](https://mail.omwom.com/)."
                    )
            else:
                mail_status.update(label=f"Mail domain ready for {mail_domain}", state="complete")

    st.subheader("Next Steps")
    st.markdown(
        f"1. Verify the site loads at `https://{p['wp_domain']}`\n"
        f"2. Log in at `https://{p['wp_domain']}/wp-admin` with the original credentials\n"
        f"3. Add the site to Uptime Kuma monitoring\n"
        f"4. Verify the site is included in the backup rotation"
    )

    if st.button("Start new restore"):
        for key in ["_backup_info", "_last_upload", "_upload_name", "_upload_size_mb",
                     "_backup_path", "_restore_done"]:
            st.session_state.pop(key, None)
        st.rerun()

    st.stop()

# ── Step 2: Backup details ──────────────────────────────
info = st.session_state._backup_info
upload_name = st.session_state._upload_name
upload_size_mb = st.session_state._upload_size_mb
backup_path = st.session_state.get("_backup_path")

size_label = f"{upload_size_mb:.1f} MB" if upload_size_mb < 1024 else f"{upload_size_mb / 1024:.1f} GB"
st.success(f"Backup parsed: **{info['site_name']}** ({upload_name}, {size_label})")

if backup_path:
    st.caption(f"Server path: `{backup_path}`")

st.subheader("Backup Contents")

col1, col2, col3 = st.columns(3)
col1.metric("Original Domain", info["old_domain"])
col2.metric("WordPress Version", info["wp_version"])
col3.metric("Softaculous Version", info["softaculous_version"])

col4, col5, col6 = st.columns(3)
col4.metric("Site Name", info["site_name"])
col5.metric("Table Prefix", info["db_prefix"])
col6.metric("Admin User", info["admin_username"])

detail_left, detail_right = st.columns(2)
with detail_left:
    st.caption(f"Original URL: `{info['old_url']}`")
    st.caption(f"Original path: `{info['original_path']}`")
    st.caption(f"Admin email: `{info['admin_email']}`")
with detail_right:
    db_icon = "🟢" if info["has_database_dump"] else "🔴"
    dir_icon = "🟢" if info["backup_dir"] else "🔴"
    st.caption(f"{db_icon} Database dump included")
    st.caption(f"{dir_icon} Site files included")
    st.caption(f"Metadata file: `{info['metadata_file']}`")

if not info["has_database_dump"]:
    st.warning("This backup does not include a database dump. The restore will only copy files.")

st.divider()

# ── Step 3: Restore target ──────────────────────────────
st.subheader("Restore Target")
st.caption("Configure where this site should be restored on the server.")

wp_name = st.text_input(
    "Site identifier",
    max_chars=16,
    help="Lowercase alphanumeric, 2-16 chars.",
    placeholder="slowbread",
    key="restore_wp_name",
)
wp_domain = st.text_input(
    "New domain",
    value=info["old_domain"],
    help="The domain where this site will be hosted.",
    key="restore_wp_domain",
)
wp_php = st.selectbox(
    "PHP version",
    ["8.2", "8.3"],
    index=1,
    key="restore_wp_php",
)

# ── Validation feedback ─────────────────────────────────
name_valid = bool(wp_name and re.match(r"^[a-z][a-z0-9_]{1,15}$", wp_name))
domain_valid = bool(
    wp_domain and re.match(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z]{2,})+$", wp_domain)
)

if wp_name and not name_valid:
    st.warning("Site identifier must be 2-16 lowercase alphanumeric characters, starting with a letter.")
if wp_domain and not domain_valid:
    st.warning("Please enter a valid domain name (e.g., example.com).")

st.markdown("**Email setup** (optional)")
restore_add_mail = st.checkbox(
    "Also create mail domain",
    value=True,
    key="restore_add_mail",
    help="Adds the domain to Modoboa so it can receive email.",
)
restore_add_mailboxes = st.checkbox(
    "Create default mailboxes (postmaster, info)",
    value=True,
    key="restore_add_mailboxes",
    disabled=not restore_add_mail,
)

# ── Restore button ──────────────────────────────────────
if st.button("Restore site", type="primary", disabled=not (name_valid and domain_valid)):
    log_activity(
        category="wordpress",
        action="restore_triggered",
        detail=(
            f"Restoring {info['site_name']} ({info['old_domain']}) "
            f"as {wp_name} at {wp_domain} from {upload_name}"
        ),
    )

    st.session_state._restore_done = {
        "wp_name": wp_name,
        "wp_domain": wp_domain,
        "wp_php": wp_php,
        "old_domain": info["old_domain"],
        "site_name": info["site_name"],
        "add_mail": restore_add_mail,
        "add_mailboxes": restore_add_mailboxes,
        "file_name": upload_name,
        "file_size_mb": upload_size_mb,
        "backup_path": backup_path,
    }
    st.rerun()
