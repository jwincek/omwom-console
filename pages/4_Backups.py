import streamlit as st
import pandas as pd
from datetime import datetime, timezone

from lib.mock_backups import (
    get_backup_history,
    get_database_backups,
    get_file_backups,
    get_provider_status,
    get_verification_history,
    get_restore_tests,
)

st.set_page_config(page_title="Backups - OMWOM Console", page_icon=":satellite:", layout="wide")

st.title("Backup Status")
st.caption("3-2-1 backup strategy: 3 copies, 2 storage types, 1 off-site")

now = datetime.now(timezone.utc)

# ── Summary metrics ─────────────────────────────────────
history = get_backup_history()
latest = history[0]
providers = get_provider_status()
db_backups = get_database_backups()

latest_status_icon = {"success": "🟢", "partial": "🟠", "failed": "🔴"}.get(
    latest["status"], "⚪"
)
hours_since = (now - latest["date"]).total_seconds() / 3600

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Last Backup", f"{hours_since:.0f}h ago")
m2.metric("Status", f"{latest_status_icon} {latest['status'].title()}")
m3.metric("Databases", f"{latest['databases']}")
m4.metric("Total Size", f"{latest['size_mb']:,} MB")
m5.metric("Providers", f"{sum(1 for p in providers if p['status'] == 'synced')}/{len(providers)} synced")

st.divider()

# ── Backup history chart ────────────────────────────────
st.subheader("Backup History (14 days)")

chart_data = pd.DataFrame([
    {
        "Date": h["date"].strftime("%m/%d"),
        "Size (MB)": h["size_mb"],
        "Duration (min)": round(h["duration_sec"] / 60, 1),
        "Databases": h["databases"],
        "Status": h["status"],
    }
    for h in reversed(history)
])

tab_chart, tab_table = st.tabs(["Chart", "Table"])

with tab_chart:
    st.bar_chart(chart_data.set_index("Date")["Size (MB)"])

with tab_table:
    def highlight_backup_status(row):
        if row["Status"] == "failed":
            return ["background-color: #fee2e2"] * len(row)
        elif row["Status"] == "partial":
            return ["background-color: #fef3c7"] * len(row)
        return [""] * len(row)

    st.dataframe(
        chart_data.style.apply(highlight_backup_status, axis=1),
        use_container_width=True,
        hide_index=True,
    )

st.divider()

# ── Database backups ────────────────────────────────────
left, right = st.columns(2)

with left:
    st.subheader("Database Backups")

    for db in db_backups:
        hours_ago = (now - db["last_backup"]).total_seconds() / 3600
        checksum_icon = "🟢" if db["checksum_ok"] else "🔴"
        db_type_label = "MySQL" if db["type"] == "mariadb" else "PG"

        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 1, 1])
            c1.markdown(f"**{db['database']}** ({db_type_label})")
            c2.caption(f"{db['size_mb']} MB")
            c3.caption(f"{checksum_icon} {hours_ago:.0f}h ago")

# ── File backups ────────────────────────────────────────
with right:
    st.subheader("File Backups")

    file_backups = get_file_backups()
    for fb in file_backups:
        hours_ago = (now - fb["last_backup"]).total_seconds() / 3600
        age_icon = "🟢" if hours_ago < 48 else ("🟠" if hours_ago < 168 else "🔴")

        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 1, 1])
            c1.markdown(f"**{fb['name']}**")
            c2.caption(f"{fb['size_mb']:,} MB")
            c3.caption(f"{age_icon} {hours_ago:.0f}h ago")
            st.caption(f"`{fb['path']}` — {fb['files']:,} files")

st.divider()

# ── Remote providers ────────────────────────────────────
st.subheader("Remote Providers")

prov_cols = st.columns(len(providers))
for i, prov in enumerate(providers):
    with prov_cols[i]:
        sync_hours = (now - prov["last_sync"]).total_seconds() / 3600
        sync_icon = "🟢" if prov["status"] == "synced" else "🔴"

        with st.container(border=True):
            st.markdown(f"**{prov['name']}**")
            st.caption(f"{sync_icon} {prov['status'].title()} — {sync_hours:.0f}h ago")
            st.caption(f"Size: {prov['total_size_gb']:.1f} GB ({prov['file_count']} files)")
            st.caption(f"Retention: {prov['retention_days']} days")
            st.caption(f"Est. cost: ${prov['monthly_cost']:.2f}/mo")

st.divider()

# ── Verification & restore tests ────────────────────────
ver_col, restore_col = st.columns(2)

with ver_col:
    st.subheader("Verification History")

    verifications = get_verification_history()
    ver_data = []
    for v in verifications:
        status_icon = "🟢" if v["status"] == "passed" else "🟠"
        ver_data.append({
            "Date": v["date"].strftime("%Y-%m-%d"),
            "Type": v["type"].title(),
            "Status": f"{status_icon} {v['status'].title()}",
            "Files": v["files_checked"],
            "Errors": v["errors"],
            "Time": f"{v['duration_sec']}s",
        })

    st.dataframe(pd.DataFrame(ver_data), use_container_width=True, hide_index=True)

with restore_col:
    st.subheader("Restore Tests")

    restore_tests = get_restore_tests()
    if restore_tests:
        for rt in restore_tests:
            status_icon = "🟢" if rt["status"] == "passed" else "🔴"
            with st.container(border=True):
                st.markdown(f"{status_icon} **{rt['database']}** — {rt['date'].strftime('%Y-%m-%d')}")
                st.caption(
                    f"Restored in {rt['restore_time_sec']}s | "
                    f"Row count match: {'Yes' if rt['row_count_match'] else 'No'}"
                )

        next_test = "1st of next month (per cron schedule)"
        st.caption(f"Next scheduled restore test: {next_test}")
    else:
        st.info("No restore tests recorded yet.")

    st.markdown("")
    st.caption(
        "Restore tests run monthly via `backup_verify.py restore-test`. "
        "They restore a random database to a temporary instance, verify row counts, "
        "then drop the test database."
    )

# ── Cron schedule reference ─────────────────────────────
st.divider()
with st.expander("Backup schedule reference"):
    st.markdown(
        "| Time | Task | Script |\n"
        "|------|------|--------|\n"
        "| 2:00 AM daily | Full backup run | `backup_manager.py` |\n"
        "| 5:00 AM daily | Local checksum verification | `backup_verify.py local` |\n"
        "| 6:00 AM Sunday | Remote provider verification | `backup_verify.py remote` |\n"
        "| 7:00 AM 1st of month | Restore test | `backup_verify.py restore-test` |\n"
        "| 3:00 AM Sunday | Config backup (tar) | cron |\n"
    )
    st.caption("Schedule defined in `/etc/cron.d/omwom-all`")
