import json

import pandas as pd
import streamlit as st

import repository as repo
from layout import TEAL, colored_heading, page_header


page_header(
    "Data Management",
    "Database",
    "Inspect database records, edit/archive rows, and review recent changes.",
)

table = st.selectbox("Table Selection", repo.TABLES)

records = repo.table_records(table, include_archived=True, limit=10000)
df = pd.DataFrame(records)
if df.empty:
    st.info("No records found.")
else:
    st.dataframe(df, hide_index=True, use_container_width=True)

if records:
    labels = {repo.record_label(table, record): record for record in records}
    selected_label = st.selectbox("Select record", labels)
    selected = labels[selected_label]
    pk_values = {column: selected[column] for column in repo.PK_COLUMNS[table]}

    colored_heading("Edit / Archive Record", TEAL)
    with st.form("edit_record", clear_on_submit=True):
        changes = {}
        for column in repo.EDITABLE_COLUMNS[table]:
            if column in repo.PK_COLUMNS[table]:
                continue
            current = selected.get(column)
            if column in {"notes", "accessibility"}:
                changes[column] = st.text_area(column, value="" if current is None else str(current))
            elif column == "status" and table == "partners":
                changes[column] = st.selectbox(column, repo.PARTNER_STATUSES, index=repo.PARTNER_STATUSES.index(current or "Active"))
            elif column == "status" and table == "event_registration":
                changes[column] = st.selectbox(column, repo.REGISTRATION_STATUSES, index=repo.REGISTRATION_STATUSES.index(current or "Registered"))
            elif column == "attendance_status":
                changes[column] = st.selectbox(column, repo.ATTENDANCE_STATUSES, index=repo.ATTENDANCE_STATUSES.index(current or "Not Checked In"))
            elif column == "channel":
                changes[column] = st.selectbox(column, repo.CHANNELS, index=repo.CHANNELS.index(current or "Connect"))
            elif column == "role":
                changes[column] = st.selectbox(column, repo.ROLES, index=repo.ROLES.index(current or "Guest"))
            elif column in {"is_archived", "need_buddy", "whatsapp_groupchat", "have_connect", "marketing_subs"}:
                changes[column] = st.selectbox(column, [None, 0, 1], index=[None, 0, 1].index(current if current in [None, 0, 1] else int(current)))
            else:
                changes[column] = st.text_input(column, value="" if current is None else str(current))

        c1, c2 = st.columns(2)
        save = c1.form_submit_button("Save changes", use_container_width=True, type="primary")
        archive = c2.form_submit_button("Archive", use_container_width=True, type="secondary")
    if save:
        changed = repo.update_record(table, pk_values, changes)
        st.success(f"Saved changes. Rows updated: {changed}.")
        st.rerun()
    if archive:
        changed = repo.archive_record(table, pk_values)
        st.success(f"Archived/cancelled selected record. Rows updated: {changed}.")
        st.rerun()

    if table in repo.TRANSACTION_TABLES:
        st.subheader("Delete transactional row")
        st.warning("This permanently deletes transactional data. Use archive/cancel when you only want to hide or cancel.")
        confirm_delete = st.checkbox("I confirm I want to delete this transactional row")
        if st.button("Delete selected transactional row", disabled=not confirm_delete):
            changed = repo.delete_transactional_record(table, pk_values)
            st.success(f"Deleted transactional row(s). Main rows deleted: {changed}.")
            st.rerun()

colored_heading("Recent Audit History", TEAL)
entries = repo.audit_entries(5, table_name=table)
audit_df = pd.DataFrame(entries)
if audit_df.empty:
    st.info("No audit entries for this table yet.")
else:
    st.dataframe(
        audit_df[["audit_id", "changed_at", "table_name", "record_id", "action", "operator", "undone"]],
        hide_index=True,
        use_container_width=True,
    )
    selected_audit_id = st.selectbox("Inspect / Undo Action", audit_df["audit_id"].tolist())
    entry = next(row for row in entries if row["audit_id"] == selected_audit_id)
    c1, c2 = st.columns(2)
    with c1:
        st.caption("Before")
        st.json(json.loads(entry["before_json"]) if entry.get("before_json") else None)
    with c2:
        st.caption("After")
        st.json(json.loads(entry["after_json"]) if entry.get("after_json") else None)

    can_undo = entry["action"] == "UPDATE" and not int(entry.get("undone") or 0)
    if st.button("Undo Action", disabled=not can_undo, type="primary"):
        try:
            undo_id = repo.undo_update(selected_audit_id)
            st.success(f"Undo applied. New audit entry: {undo_id}.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
