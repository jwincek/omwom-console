import re
import streamlit as st

from lib.database import log_activity
from lib.softaculous import parse_backup_file

st.set_page_config(page_title="Restore - OMWOM Console", page_icon=":satellite:")

st.title("WordPress Restore")
st.caption("Restore a WordPress site from a Softaculous backup archive")

# ── Step 1: Upload ──────────────────────────────────────
uploaded = st.file_uploader(
    "Softaculous backup (.tar.gz)",
    type=["gz"],
    help="Upload a .tar.gz backup from Softaculous WordPress Manager",
)

if uploaded:
    if st.session_state.get("_last_upload") != uploaded.name:
        with st.spinner("Parsing backup metadata..."):
            info = parse_backup_file(uploaded.getvalue())

        if info is None:
            st.error("Could not parse this file. Is it a Softaculous WordPress Manager backup?")
            st.stop()

        st.session_state._backup_info = info
        st.session_state._last_upload = uploaded.name
        st.session_state._upload_name = uploaded.name
        st.session_state._upload_size_mb = uploaded.size / 1024 / 1024
        st.session_state.pop("_restore_done", None)

# ── Show instructions if no backup parsed yet ───────────
if "_backup_info" not in st.session_state:
    st.markdown(
        "Upload a `.tar.gz` backup file from Softaculous WordPress Manager.\n\n"
        "The restore process will:"
    )
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

    with st.status("Restoring WordPress site...", expanded=True) as status:
        st.write(f"📦 Backup: {p['file_name']} ({p['file_size_mb']:.1f} MB)")
        st.write(f"🌐 Source: {p['old_domain']} → {p['wp_domain']}")
        st.write(f"🔧 Site ID: {p['wp_name']}, PHP {p['wp_php']}")
        st.write("")
        st.write(
            "In production, this uploads the backup to "
            "`/srv/restore-staging/` and calls the Semaphore API "
            "to trigger `wordpress-restore.yml` with these parameters:"
        )
        st.code(
            f"wp_name: {p['wp_name']}\n"
            f"wp_domain: {p['wp_domain']}\n"
            f"wp_php: {p['wp_php']}\n"
            f"backup_file: /srv/restore-staging/{p['file_name']}",
            language="yaml",
        )
        status.update(label="Restore simulated (mock mode)", state="complete")

    st.subheader("Next Steps")
    st.markdown(
        f"1. Verify the site loads at `https://{p['wp_domain']}`\n"
        f"2. Log in at `https://{p['wp_domain']}/wp-admin` with the original credentials\n"
        f"3. Add the site to Uptime Kuma monitoring\n"
        f"4. Verify the site is included in the backup rotation"
    )

    if st.button("Start new restore"):
        for key in ["_backup_info", "_last_upload", "_upload_name", "_upload_size_mb", "_restore_done"]:
            st.session_state.pop(key, None)
        st.rerun()

    st.stop()

# ── Step 2: Backup details ──────────────────────────────
info = st.session_state._backup_info
upload_name = st.session_state._upload_name
upload_size_mb = st.session_state._upload_size_mb

st.success(f"Backup parsed: **{info['site_name']}** ({upload_name}, {upload_size_mb:.1f} MB)")

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
        "file_name": upload_name,
        "file_size_mb": upload_size_mb,
    }
    st.rerun()
