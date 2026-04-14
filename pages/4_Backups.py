import streamlit as st
import pandas as pd
from datetime import datetime, timezone

from lib.database import log_activity
from lib.semaphore import get_client
from lib.backups import (
    get_backup_history,
    get_database_backups,
    get_file_backups,
    get_provider_status,
    get_verification_history,
    get_restore_tests,
    real_data_available,
)

st.set_page_config(page_title="Backups - OMWOM Console", page_icon=":satellite:", layout="wide")

st.title("Backup Status")
if real_data_available():
    st.caption("3-2-1 backup strategy: 3 copies, 2 storage types, 1 off-site")
else:
    st.caption("3-2-1 backup strategy — 🟠 Reading mock data (no /var/backups/last_run.json found)")

client = get_client()
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

# ── Manual backup ───────────────────────────────────────
with st.expander("Run backup now"):
    st.caption("Trigger an on-demand backup via Semaphore. Uses the same `backup_manager.py` as the daily cron.")

    scope = st.radio(
        "Scope",
        ["Full backup", "Databases only", "Files only", "Single database"],
        horizontal=True,
        key="backup_scope",
    )

    selected_db = None
    if scope == "Single database":
        db_names = [db["database"] for db in db_backups]
        selected_db = st.selectbox("Database", db_names, key="backup_single_db")

    skip_upload = st.checkbox("Skip remote upload", key="backup_skip_upload",
                              help="Run the backup locally without uploading to Backblaze/Hetzner. Useful for quick pre-change snapshots.")

    extra_vars = {}
    if scope == "Databases only":
        extra_vars["backup_scope"] = "databases"
    elif scope == "Files only":
        extra_vars["backup_scope"] = "files"
    elif scope == "Single database":
        extra_vars["backup_scope"] = "single"
        extra_vars["backup_database"] = selected_db
    if skip_upload:
        extra_vars["backup_skip_upload"] = True

    if st.button("Run backup", type="primary", key="btn_run_backup"):
        scope_desc = scope.lower()
        if selected_db:
            scope_desc = f"{selected_db} only"
        if skip_upload:
            scope_desc += " (local only)"

        log_activity("backup", "backup_triggered", f"Manual backup: {scope_desc}")

        if client.mock_mode:
            with st.status("Running backup...", expanded=True) as status:
                st.write(f"Scope: {scope_desc}")
                if extra_vars:
                    st.code(
                        "\n".join(f"{k}: {v}" for k, v in extra_vars.items()),
                        language="yaml",
                    )
                st.write("Mock: would trigger `backup-run.yml` via Semaphore")
                status.update(label="Backup simulated (mock mode)", state="complete")
        else:
            task = client.run_playbook("backup-run.yml", extra_vars=extra_vars)
            with st.status("Running backup...", expanded=True) as status:
                st.write(f"Scope: {scope_desc}")
                st.write(f"Semaphore task #{task['id']} started")
                result = client.wait_for_task(task["id"])
                if result["status"] == "success":
                    status.update(label="Backup complete", state="complete")
                    log_activity("backup", "backup_completed", f"Manual backup succeeded: {scope_desc}")
                else:
                    status.update(label="Backup failed", state="error")
                    log_activity("backup", "backup_failed", f"Manual backup failed: {scope_desc}", status="error")

    # ── Verify backups button ───────────────────────────
    st.divider()
    st.caption("Run an on-demand verification of local backup checksums.")

    if st.button("Verify backups", key="btn_verify_backup"):
        log_activity("backup", "verify_triggered", "Manual verification")

        if client.mock_mode:
            with st.status("Verifying backups...", expanded=True) as status:
                st.write("Mock: would trigger `backup-verify.yml` via Semaphore")
                status.update(label="Verification simulated (mock mode)", state="complete")
        else:
            task = client.run_playbook("backup-verify.yml")
            with st.status("Verifying backups...", expanded=True) as status:
                st.write(f"Semaphore task #{task['id']} started")
                result = client.wait_for_task(task["id"])
                if result["status"] == "success":
                    status.update(label="Verification complete", state="complete")
                else:
                    status.update(label="Verification failed", state="error")

st.divider()

# ── Backup history ──────────────────────────────────────
import altair as alt

range_col, rate_col = st.columns([2, 1])
with range_col:
    history_days = st.radio(
        "History range",
        [7, 14, 30],
        index=1,
        horizontal=True,
        key="history_range",
        format_func=lambda d: f"{d} days",
    )

history = get_backup_history(days=history_days)

success_count = sum(1 for h in history if h["status"] == "success")
with rate_col:
    success_rate = (success_count / len(history)) * 100 if history else 0
    st.metric("Success Rate", f"{success_count}/{len(history)} ({success_rate:.0f}%)")

st.subheader(f"Backup History ({history_days} days)")

chart_rows = []
for h in reversed(history):
    prev_idx = next((j for j, hh in enumerate(reversed(history)) if hh["date"] < h["date"]), None)
    prev_size = list(reversed(history))[prev_idx]["size_mb"] if prev_idx is not None else h["size_mb"]
    delta = h["size_mb"] - prev_size

    mins = h["duration_sec"] // 60
    secs = h["duration_sec"] % 60

    status_icon = {"success": "🟢", "partial": "🟠", "failed": "🔴"}.get(h["status"], "⚪")

    chart_rows.append({
        "Date": h["date"].strftime("%m/%d"),
        "Size (MB)": h["size_mb"],
        "Duration": f"{mins}m {secs}s",
        "Duration (sec)": h["duration_sec"],
        "Databases": h["databases"],
        "Files": h["files"],
        "Status": h["status"],
        "Status Icon": f"{status_icon} {h['status']}",
        "Delta": f"{'+' if delta >= 0 else ''}{delta} MB",
        "error_detail": h.get("error_detail", ""),
    })

chart_data = pd.DataFrame(chart_rows)

tab_chart, tab_dual, tab_table = st.tabs(["Size", "Size + Duration", "Table"])

with tab_chart:
    color_scale = alt.Scale(
        domain=["success", "partial", "failed"],
        range=["#22c55e", "#f59e0b", "#ef4444"],
    )

    bars = alt.Chart(chart_data).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        x=alt.X("Date:N", sort=None, title="Date"),
        y=alt.Y("Size (MB):Q", title="Size (MB)"),
        color=alt.Color("Status:N", scale=color_scale, legend=alt.Legend(title="Status")),
        tooltip=["Date", "Size (MB)", "Status", "Duration", "Databases", "Delta"],
    ).properties(height=350)

    st.altair_chart(bars, width="stretch")

with tab_dual:
    base = alt.Chart(chart_data).encode(
        x=alt.X("Date:N", sort=None, title="Date"),
    )

    bars = base.mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3, opacity=0.7).encode(
        y=alt.Y("Size (MB):Q", title="Size (MB)"),
        color=alt.Color("Status:N", scale=color_scale, legend=alt.Legend(title="Status")),
        tooltip=["Date", "Size (MB)", "Status", "Delta"],
    )

    line = base.mark_line(color="#1a3a5c", strokeWidth=2, point=True).encode(
        y=alt.Y("Duration (sec):Q", title="Duration (seconds)"),
        tooltip=["Date", "Duration", "Status"],
    )

    dual = alt.layer(bars, line).resolve_scale(y="independent").properties(height=350)

    st.altair_chart(dual, width="stretch")
    st.caption("Bars = backup size (left axis) · Line = duration (right axis)")

with tab_table:
    table_data = chart_data[["Date", "Status Icon", "Size (MB)", "Delta", "Duration", "Databases", "Files"]].copy()
    table_data = table_data.rename(columns={"Status Icon": "Status"})

    def highlight_backup_status(row):
        status_text = row["Status"]
        if "failed" in status_text:
            return ["background-color: #fee2e2"] * len(row)
        elif "partial" in status_text:
            return ["background-color: #fef3c7"] * len(row)
        return [""] * len(row)

    st.dataframe(
        table_data.style.apply(highlight_backup_status, axis=1),
        width="stretch",
        hide_index=True,
    )

# ── Failed/partial day details ──────────────────────────
problem_days = [r for r in chart_rows if r["error_detail"]]
if problem_days:
    st.subheader("Issues")
    for day in problem_days:
        status_icon = {"partial": "🟠", "failed": "🔴"}.get(day["Status"], "⚪")
        with st.expander(f"{status_icon} {day['Date']} — {day['Status']}"):
            st.markdown(day["error_detail"])
            st.caption(f"Size: {day['Size (MB)']:,} MB · Duration: {day['Duration']} · DBs: {day['Databases']}/8 · Files: {day['Files']}/5")

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

status_icons = {
    "synced": "🟢",
    "disabled": "⚪",
    "error": "🔴",
    "unreachable": "🟠",
}

prov_cols = st.columns(len(providers))
for i, prov in enumerate(providers):
    with prov_cols[i]:
        sync_icon = status_icons.get(prov["status"], "🔴")

        with st.container(border=True):
            st.markdown(f"**{prov['name']}**")

            if prov["last_sync"]:
                sync_hours = (now - prov["last_sync"]).total_seconds() / 3600
                st.caption(f"{sync_icon} {prov['status'].title()} — checked {sync_hours:.0f}h ago")
            else:
                st.caption(f"{sync_icon} {prov['status'].title()}")

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

    st.dataframe(pd.DataFrame(ver_data), width="stretch", hide_index=True)

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
