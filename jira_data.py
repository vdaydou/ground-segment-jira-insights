"""Load all tickets into one pandas table: the fictional history (CSV) + the live status from Jira.

Jira is the source of truth for the tickets that live there: if someone moves a ticket on the
Jira board, the table (and later the dashboard) follows.
"""
import os

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()
JIRA_URL = os.getenv("JIRA_URL")
AUTH = (os.getenv("JIRA_EMAIL"), os.getenv("JIRA_API_TOKEN"))
PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY")

# Jira may return the status names in French (the project was created in French)
STATUS_EN = {"À faire": "To Do", "En cours": "In Progress",
             "Revue en cours": "In Review", "Terminé(e)": "Done"}
DATE_COLUMNS = ["created", "in_progress", "in_review", "done"]


def jira_search(jql, fields):
    """Run a JQL search and return every matching issue (Jira sends them page by page)."""
    issues, page_token = [], None
    while True:
        body = {"jql": jql, "fields": fields, "maxResults": 100}
        if page_token:
            body["nextPageToken"] = page_token
        response = requests.post(f"{JIRA_URL}/rest/api/3/search/jql",
                                 json=body, auth=AUTH, timeout=30)
        response.raise_for_status()
        data = response.json()
        issues += data["issues"]
        page_token = data.get("nextPageToken")
        if not page_token:  # no more pages
            return issues


def load_live_tickets():
    """Read the tickets currently in Jira and return them as a pandas table."""
    issues = jira_search(f"project = {PROJECT_KEY} ORDER BY created",
                         ["status", "labels", "statuscategorychangedate"])
    rows = []
    for issue in issues:
        fields = issue["fields"]
        # The "source-t-183" label links the Jira ticket to its row in the history
        source = next((label for label in fields["labels"] if label.startswith("source-")), None)
        rows.append({
            "id": source.removeprefix("source-").upper() if source else None,
            "jira_key": issue["key"],
            "jira_status": STATUS_EN.get(fields["status"]["name"], fields["status"]["name"]),
            "status_changed": fields.get("statuscategorychangedate"),
        })
    return pd.DataFrame(rows, columns=["id", "jira_key", "jira_status", "status_changed"])


def load_tickets():
    """Return one table with all tickets: history from the CSV, live status from Jira."""
    tickets = pd.read_csv("tickets_history.csv", parse_dates=DATE_COLUMNS)
    live = load_live_tickets()

    # Join the two tables on the ticket id (like a VLOOKUP in Excel)
    tickets = tickets.merge(live, on="id", how="left")

    # For tickets that live in Jira, Jira's status wins over the CSV
    in_jira = tickets["jira_key"].notna()
    tickets.loc[in_jira, "status"] = tickets.loc[in_jira, "jira_status"]

    # A ticket closed in Jira since the history was generated: take the date its status changed
    newly_done = in_jira & (tickets["status"] == "Done") & tickets["done"].isna()
    changed = pd.to_datetime(tickets.loc[newly_done, "status_changed"], utc=True)
    tickets.loc[newly_done, "done"] = changed.dt.tz_convert("Europe/Berlin").dt.tz_localize(None)

    return tickets.drop(columns=["jira_status", "status_changed"])


if __name__ == "__main__":
    # Only runs when this file is launched directly (not when the dashboard imports it)
    pd.set_option("display.width", 150)
    tickets = load_tickets()
    print(f"{len(tickets)} tickets loaded, {tickets['jira_key'].notna().sum()} of them live in Jira\n")
    print(tickets[["id", "jira_key", "summary", "status", "priority"]].tail(5), "\n")
    print("Tickets per status:")
    print(tickets["status"].value_counts(), "\n")
    print("Open tickets per subsystem:")
    print(tickets[tickets["status"] != "Done"].groupby("subsystem").size())