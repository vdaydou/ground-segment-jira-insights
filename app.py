"""Web dashboard: process indicators of the fictional ground segment Jira project.

Run locally with:  streamlit run app.py
"""
import os

import altair as alt
import pandas as pd
import streamlit as st
import re

from jira_data import load_tickets
from ai_summary import weekly_summary
from metrics import (PRIORITY_ORDER, add_durations, headline_kpis, lead_time_by,
                     monthly_flow, stuck_tickets, time_per_step)

st.set_page_config(page_title="Ground Segment Jira Insights", page_icon="🛰️", layout="wide")


@st.cache_data(ttl=300)  # keep the Jira data 5 minutes, so every click does not call the API
def get_tickets():
    return add_durations(load_tickets())


# ---------- Header ----------
st.title("🛰️ Ground Segment Jira Insights")
st.caption("Process indicators for a fictional satellite ground segment, read live from Jira. "
           "All data is invented; this project is not affiliated with ESA.")
st.markdown("[View the code on GitHub](https://github.com/vdaydou/ground-segment-jira-insights)")
if st.button("🔄 Refresh from Jira"):
    st.cache_data.clear()  # forget the stored data, read Jira again
tickets = get_tickets()

# ---------- Filters (left sidebar) ----------
st.sidebar.header("Filters")
filters = {}
for column, label in [("subsystem", "Subsystem"), ("type", "Ticket type"), ("priority", "Priority")]:
    options = sorted(tickets[column].unique())
    filters[column] = st.sidebar.multiselect(label, options, default=options)
selected = tickets
for column, values in filters.items():
    selected = selected[selected[column].isin(values)]
st.sidebar.caption(f"{len(selected)} of {len(tickets)} tickets selected")

if selected.empty:
    st.warning("No ticket matches the filters.")
    st.stop()

# ---------- Headline numbers ----------
for column, (name, value) in zip(st.columns(4), headline_kpis(selected).items()):
    column.metric(name, value)

# ---------- Where does the process slow down? ----------
st.subheader("Where does the process slow down?")
steps = time_per_step(selected)
slowest = steps["median (days)"].idxmax()
chart_data = steps.reset_index(names="step").melt(id_vars="step", var_name="measure", value_name="days")
chart = alt.Chart(chart_data).mark_bar().encode(
    x=alt.X("days:Q", title="Days", scale=alt.Scale(domainMin=0)),  # axis starts at 0
    y=alt.Y("step:N", sort=list(steps.index), title=None),          # keep the process order
    yOffset="measure:N",                                            # two bars per step
    color=alt.Color("measure:N", title=None, legend=alt.Legend(orient="bottom")),
)
st.altair_chart(chart)
st.info(f"**{slowest}** is the slowest step: a typical ticket spends "
        f"{steps.loc[slowest, 'median (days)']} days there, and 1 in 10 tickets more than "
        f"{steps.loc[slowest, '90% of tickets under (days)']} days.")

# ---------- Flow and priorities ----------
left, right = st.columns(2)
with left:
    st.subheader("Tickets created vs closed per month")
    flow = monthly_flow(selected).reset_index(names="month").melt(
        id_vars="month", var_name="tickets", value_name="count")
    st.altair_chart(alt.Chart(flow).mark_bar().encode(
        x=alt.X("month:N", title=None, axis=alt.Axis(labelAngle=0)),
        xOffset="tickets:N",                                  # created and closed side by side
        y=alt.Y("count:Q", title="Tickets"),
        color=alt.Color("tickets:N", title=None, legend=alt.Legend(orient="bottom")),
    ))
    st.caption("The first and last months are incomplete (the history starts on 24 May).")
with right:
    st.subheader("Median lead time by priority")
    by_priority = lead_time_by(selected, "priority").dropna().reset_index()
    st.altair_chart(alt.Chart(by_priority).mark_bar().encode(
        x=alt.X("priority:N", sort=PRIORITY_ORDER, title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("median:Q", title="Days from creation to closure"),
        tooltip=["priority", "median", alt.Tooltip("count", title="closed tickets")],
    ))

# ---------- Tickets that need attention ----------
st.subheader("Tickets that need attention")
stuck = stuck_tickets(selected)
if stuck.empty:
    st.success("No ticket has been stuck in the same step for more than 10 days.")
else:
    jira_url = os.getenv("JIRA_URL")
    stuck["jira_key"] = jira_url + "/browse/" + stuck["jira_key"]  # clickable link to Jira
    st.dataframe(stuck, hide_index=True, column_config={
        "id": "ID",
        "jira_key": st.column_config.LinkColumn("Jira", display_text=r"browse/(.*)"),
        "summary": "Summary",
        "status": "Status",
        "priority": "Priority",
        "days_in_status": st.column_config.NumberColumn("Days in current step", format="%.1f"),
    })

# ---------- Open tickets per subsystem ----------
st.subheader("Open tickets per subsystem and status")
open_tickets = selected.loc[selected["status"] != "Done", ["subsystem", "status"]]
STATUS_ORDER = ["To Do", "In Progress", "In Review"]
st.altair_chart(alt.Chart(open_tickets).mark_bar().encode(
    x=alt.X("count():Q", title="Open tickets", axis=alt.Axis(tickMinStep=1)),
    y=alt.Y("subsystem:N", title=None, sort="-x"),            # biggest backlog on top
    color=alt.Color("status:N", sort=STATUS_ORDER, title=None,
                    scale=alt.Scale(domain=STATUS_ORDER, range=["#9ecae1", "#3182bd", "#e6550d"]),
                    legend=alt.Legend(orient="bottom")),
    order=alt.Order("status_rank:Q"),                         # stack in process order
).transform_calculate(
    status_rank="indexof(['To Do', 'In Progress', 'In Review'], datum.status)"))

# ---------- AI weekly summary ----------
st.subheader("🤖 Weekly summary written by AI")
st.caption("Written by Google Gemini from the figures above only (the model is told not to "
           "invent anything). Always check an AI summary before sharing it.")
if not os.getenv("GEMINI_API_KEY"):
    st.info("Add a GEMINI_API_KEY to enable this feature.")
elif st.button("✍️ Generate the weekly summary"):
    with st.spinner("Gemini is writing the summary..."):
        st.session_state["summary"] = weekly_summary(selected)
if "summary" in st.session_state:
    st.markdown(re.sub(r"^\s*#{1,3}\s+", "#### ", st.session_state["summary"], flags=re.M))  # smaller headings
    st.download_button("⬇️ Download as Markdown", st.session_state["summary"],
                       file_name="weekly_summary.md")