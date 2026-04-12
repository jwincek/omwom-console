import re
import streamlit as st
import pandas as pd

from lib.database import log_activity
from lib.semaphore import get_client

st.set_page_config(page_title="Health - OMWOM Console", page_icon=":satellite:", layout="wide")

st.title("Server Health")
st.caption("Run the health check playbook and view results")

client = get_client()

if client.mock_mode:
    st.caption("🟠 Running in mock mode — Semaphore not connected")

# ── Run health check ────────────────────────────────────
col_btn, col_status = st.columns([1, 3])

with col_btn:
    run_check = st.button("Run health check", type="primary")

if run_check:
    log_activity("health", "health_check_triggered", "Manual health check from console")

    with st.status("Running health check...", expanded=True) as status:
        if client.mock_mode:
            st.write("Simulating Semaphore task: `health.yml`")
            task = client.run_task(template_id=7)
            task = client.wait_for_task(task["id"])
        else:
            st.write("Triggering Semaphore task: `health.yml`")
            task = client.run_task(template_id=7)
            task = client.wait_for_task(task["id"])

        if task["status"] == "success":
            status.update(label="Health check complete", state="complete")
        else:
            status.update(label="Health check failed", state="error")

    st.session_state._health_task_id = task["id"]
    st.session_state._health_status = task["status"]

# ── Display results ─────────────────────────────────────
if "_health_task_id" not in st.session_state:
    st.info("Click **Run health check** to trigger the `health.yml` playbook via Semaphore.")
    st.stop()

task_id = st.session_state._health_task_id
task_status = st.session_state._health_status
output_lines = client.get_task_output(task_id)

# Parse the health check output into sections
sections = {}
current_section = None
for line in output_lines:
    text = line.get("output", "").strip()
    if not text:
        continue

    section_match = re.match(r"^=== (.+) ===$", text)
    if section_match:
        current_section = section_match.group(1)
        sections[current_section] = []
    elif current_section and not text.startswith("PLAY") and not text.startswith("TASK"):
        sections[current_section].append(text)

# ── System overview ─────────────────────────────────────
if "System Health Report" in sections:
    st.subheader("System Overview")

    metrics = {}
    for line in sections["System Health Report"]:
        if ":" in line:
            key, val = line.split(":", 1)
            metrics[key.strip()] = val.strip()

    m1, m2, m3, m4, m5 = st.columns(5)

    if "Uptime" in metrics:
        days_match = re.match(r"(\d+) days?", metrics["Uptime"])
        m1.metric("Uptime", f"{days_match.group(1)}d" if days_match else metrics["Uptime"])

    if "Load" in metrics:
        load_1m = metrics["Load"].split(",")[0].strip()
        m2.metric("Load (1m)", load_1m)

    if "CPU" in metrics:
        m3.metric("CPU", metrics["CPU"])

    if "RAM" in metrics:
        m4.metric("RAM", metrics["RAM"])

    if "Disk" in metrics:
        m5.metric("Disk", metrics["Disk"])

    if "Swap" in metrics:
        st.caption(f"Swap: {metrics['Swap']}")

# ── Service status ──────────────────────────────────────
if "Service Status" in sections:
    st.divider()
    st.subheader("Service Status")

    svc_data = []
    for line in sections["Service Status"]:
        parts = line.split(None, 1)
        if len(parts) == 2:
            name, status_text = parts
            is_running = "running" in status_text.lower()
            svc_data.append({
                "Service": name,
                "Status": status_text,
                "OK": "🟢" if is_running else "🔴",
            })

    if svc_data:
        svc_cols = st.columns(len(svc_data))
        for i, svc in enumerate(svc_data):
            svc_cols[i].markdown(f"{svc['OK']}\n\n**{svc['Service']}**")

# ── Docker containers ───────────────────────────────────
if "Docker Containers" in sections:
    st.divider()
    st.subheader("Docker Containers")

    docker_data = []
    for line in sections["Docker Containers"]:
        parts = line.split(None, 1)
        if len(parts) == 2:
            name, status_text = parts
            is_running = "running" in status_text.lower()
            docker_data.append({
                "Container": name,
                "Status": status_text,
                "OK": "🟢" if is_running else "🔴",
            })

    if docker_data:
        d_cols = st.columns(max(len(docker_data), 1))
        for i, d in enumerate(docker_data):
            d_cols[i].markdown(f"{d['OK']}\n\n**{d['Container']}**")

# ── SSL certificates ───────────────────────────────────
if "SSL Certificates" in sections:
    st.divider()
    st.subheader("SSL Certificates")

    cert_data = []
    for line in sections["SSL Certificates"]:
        parts = re.match(r"^(\S+)\s+(\d+) days remaining\s+(\w+)", line)
        if parts:
            domain, days, status = parts.groups()
            cert_data.append({
                "Domain": domain,
                "Days Remaining": int(days),
                "Status": status,
            })

    if cert_data:
        cert_df = pd.DataFrame(cert_data)

        def highlight_cert(row):
            if row["Status"] == "CRITICAL":
                return ["background-color: #fee2e2"] * len(row)
            elif row["Status"] == "WARNING":
                return ["background-color: #fef3c7"] * len(row)
            return [""] * len(row)

        st.dataframe(
            cert_df.style.apply(highlight_cert, axis=1),
            width="stretch",
            hide_index=True,
        )

# ── Backup status ──────────────────────────────────────
if "Backup Status" in sections:
    st.divider()
    st.subheader("Backup Status")

    for line in sections["Backup Status"]:
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()

            if "SUCCESS" in val or "PASSED" in val or "synced" in val:
                st.caption(f"🟢 **{key}:** {val}")
            elif "FAILED" in val or "ERROR" in val:
                st.caption(f"🔴 **{key}:** {val}")
            else:
                st.caption(f"**{key}:** {val}")

# ── Raw output ──────────────────────────────────────────
st.divider()
with st.expander("Raw playbook output"):
    raw_text = "\n".join(line.get("output", "") for line in output_lines)
    st.code(raw_text, language="text")

# ── Task history ────────────────────────────────────────
st.divider()
st.subheader("Recent Tasks")

tasks = client.get_tasks(limit=10)
template_map = {t["id"]: t["name"] for t in client.get_templates()}

task_data = []
for t in tasks:
    status_icon = {"success": "🟢", "error": "🔴", "waiting": "🟡", "running": "🔵"}.get(
        t.get("status", ""), "⚪"
    )
    task_data.append({
        "Status": f"{status_icon} {t.get('status', 'unknown')}",
        "Template": template_map.get(t.get("template_id"), f"#{t.get('template_id')}"),
        "Started": t.get("start", "")[:19].replace("T", " "),
        "Task ID": t.get("id"),
    })

if task_data:
    st.dataframe(pd.DataFrame(task_data), width="stretch", hide_index=True)

# ── Sidebar ─────────────────────────────────────────────
with st.sidebar:
    st.divider()
    st.caption(f"Task #{task_id}: {task_status}")
    if client.mock_mode:
        st.caption("Mode: Mock")
        st.caption("Set SEMAPHORE_URL and SEMAPHORE_TOKEN env vars to connect.")
    else:
        st.caption(f"Semaphore: {client.config.base_url}")
