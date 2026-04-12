import re
import streamlit as st

from lib.mock_logs import get_log_sources, get_log_content

st.set_page_config(page_title="Logs - OMWOM Console", page_icon=":satellite:", layout="wide")

st.title("Log Viewer")
st.caption("View and search server logs")

sources = get_log_sources()
source_names = [s["name"] for s in sources]

# ── Source selector ─────────────────────────────────────
col_source, col_lines, col_filter = st.columns([2, 1, 3])

selected_source = col_source.selectbox(
    "Log source",
    source_names,
    key="log_source",
)

tail_lines = col_lines.number_input(
    "Lines",
    min_value=10,
    max_value=1000,
    value=100,
    step=50,
    key="log_lines",
    help="Number of lines to display (tail)",
)

filter_text = col_filter.text_input(
    "Filter",
    placeholder="e.g. ERROR, slowbirdbread, 203.0.113",
    key="log_filter",
    help="Filter lines containing this text (case-insensitive)",
)

# Show source info
source_info = next(s for s in sources if s["name"] == selected_source)
st.caption(f"`{source_info['file']}` — {source_info['description']}")

st.divider()

# ── Log content ─────────────────────────────────────────
raw_content = get_log_content(selected_source, tail_lines=tail_lines)
lines = raw_content.split("\n")

if filter_text:
    pattern = re.compile(re.escape(filter_text), re.IGNORECASE)
    filtered_lines = [line for line in lines if pattern.search(line)]
    st.caption(f"Showing {len(filtered_lines)} of {len(lines)} lines matching \"{filter_text}\"")
    lines = filtered_lines

if not lines or (len(lines) == 1 and not lines[0].strip()):
    st.info("No log entries to display.")
else:
    # Highlight severity levels
    highlighted = []
    for line in lines:
        if any(kw in line.upper() for kw in ["ERROR", "CRITICAL", "FATAL", "FAIL", "Ban "]):
            highlighted.append(f"🔴 {line}")
        elif any(kw in line.upper() for kw in ["WARN", "WARNING", "PARTIAL"]):
            highlighted.append(f"🟠 {line}")
        elif any(kw in line.upper() for kw in ["SUCCESS", "PASSED", "OK", "COMPLETE"]):
            highlighted.append(f"🟢 {line}")
        else:
            highlighted.append(f"   {line}")

    display_text = "\n".join(highlighted)

    st.code(display_text, language="log", line_numbers=True)

    # ── Quick stats ─────────────────────────────────────
    total = len(lines)
    errors = sum(1 for l in lines if any(kw in l.upper() for kw in ["ERROR", "CRITICAL", "FATAL", "FAIL"]))
    warnings = sum(1 for l in lines if any(kw in l.upper() for kw in ["WARN", "WARNING"]))
    bans = sum(1 for l in lines if "Ban " in l)

    if errors or warnings or bans:
        stat_cols = st.columns(4)
        stat_cols[0].metric("Total Lines", total)
        if errors:
            stat_cols[1].metric("Errors", errors)
        if warnings:
            stat_cols[2].metric("Warnings", warnings)
        if bans:
            stat_cols[3].metric("Bans", bans)

# ── Quick filters ───────────────────────────────────────
st.divider()
st.caption("Quick filters:")
qf_cols = st.columns(6)

quick_filters = {
    "Errors only": "ERROR",
    "Warnings": "WARN",
    "Bans": "Ban",
    "Slowbirdbread": "slowbirdbread",
    "Odoo": "odoo",
    "Rejected": "reject",
}

for i, (label, value) in enumerate(quick_filters.items()):
    if qf_cols[i].button(label, key=f"qf_{value}"):
        st.session_state.log_filter = value
        st.rerun()
