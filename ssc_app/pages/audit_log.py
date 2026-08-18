import pandas as pd
import streamlit as st

import repository as repo
from layout import page_header


page_header(
    "Data Management",
    "Audit Log",
    "Track what changed, when it changed, and who made the change.",
)

table_filter = st.selectbox("Filter table", ["All"] + repo.TABLES)
operators = ["All"] + repo.audit_operators()
operator_filter = st.selectbox("Filter people", operators)
duration_options = {
    "All time": "All",
    "Last 7 days": 7,
    "Last 30 days": 30,
    "Last 90 days": 90,
}
duration_label = st.selectbox("Filter time duration", list(duration_options))
entries = repo.audit_entries(
    10000,
    table_name=table_filter,
    operator_name=operator_filter,
    days=duration_options[duration_label],
)

if not entries:
    st.info("No audit entries yet.")
    st.stop()

df = pd.DataFrame(entries)
df["what_changed"] = [repo.audit_change_summary(row) for row in entries]
st.dataframe(
    df[["changed_at", "operator", "table_name", "record_id", "action", "what_changed", "undone", "undo_audit_id"]],
    hide_index=True,
    use_container_width=True,
)

selected_id = st.selectbox("Inspect entry", df["audit_id"].tolist())
entry = next(row for row in entries if row["audit_id"] == selected_id)

c1, c2 = st.columns(2)
with c1:
    st.subheader("Before")
    st.json(repo.audit_payload(entry, "before_json"))
with c2:
    st.subheader("After")
    st.json(repo.audit_payload(entry, "after_json"))
