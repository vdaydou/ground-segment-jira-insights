"""Create the tickets that are still open in the fictional history inside the real Jira project.

Each ticket gets its priority, labels (type and subsystem), its fictional creation date in the
"Start date" field, and is then moved to the right status. Running the script twice does not
create duplicates: tickets already sent are recognised by their "source-..." label.
"""
import csv
import os

import requests
from dotenv import load_dotenv

load_dotenv()
JIRA_URL = os.getenv("JIRA_URL")
AUTH = (os.getenv("JIRA_EMAIL"), os.getenv("JIRA_API_TOKEN"))
PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY")

# Our statuses -> the names they may have in Jira (English, or French if the project was created in French)
STATUS_NAMES = {"In Progress": ["In Progress", "En cours"],
                "In Review": ["In Review", "Revue en cours"],
                "Done": ["Done", "Terminé(e)"]}
# Default Jira Cloud priority ids
PRIORITY_IDS = {"Highest": "1", "High": "2", "Medium": "3", "Low": "4"}


def jira(method, path, **kwargs):
    """Send a request to the Jira API, stop with a clear message if it fails."""
    response = requests.request(method, f"{JIRA_URL}{path}", auth=AUTH, timeout=30, **kwargs)
    if not response.ok:
        raise SystemExit(f"Jira error {response.status_code} on {path}: {response.text}")
    return response.json() if response.text else None


def slug(text):
    """'Orbit & Time Processing' -> 'orbit-time-processing' (labels cannot contain spaces)."""
    return "-".join(text.lower().replace("&", " ").split())


# 1. Find the id of the "Task" issue type and of the "Start date" field
types = jira("GET", f"/rest/api/3/issue/createmeta/{PROJECT_KEY}/issuetypes")["issueTypes"]
task_type_id = next(t["id"] for t in types if t["name"] in ("Task", "Tâche"))
fields = jira("GET", f"/rest/api/3/issue/createmeta/{PROJECT_KEY}/issuetypes/{task_type_id}")["fields"]
start_date_field = next(f["fieldId"] for f in fields if f["name"] in ("Start date", "Date de début"))

# 2. Read the open tickets from the history
with open("tickets_history.csv", encoding="utf-8") as f:
    open_tickets = [row for row in csv.DictReader(f) if row["status"] != "Done"]
print(f"{len(open_tickets)} open tickets to send")

for row in open_tickets:
    source_label = f"source-{row['id'].lower()}"

    # 3. Skip the ticket if it was already sent
    found = jira("POST", "/rest/api/3/search/jql",
                 json={"jql": f'project = {PROJECT_KEY} AND labels = "{source_label}"',
                       "maxResults": 1, "fields": ["key"]})
    if found["issues"]:
        print(f"{row['id']} already in Jira as {found['issues'][0]['key']}, skipped")
        continue

    # 4. Create the ticket
    description = (f"Fictional ticket {row['id']} ({row['type']}, {row['subsystem']}), "
                   f"created on {row['created']}.")
    issue = jira("POST", "/rest/api/3/issue", json={"fields": {
        "project": {"key": PROJECT_KEY},
        "issuetype": {"id": task_type_id},
        "summary": row["summary"],
        "priority": {"id": PRIORITY_IDS[row["priority"]]},
        "labels": [slug(row["type"]), slug(row["subsystem"]), source_label],
        start_date_field: row["created"][:10],  # only the date part, e.g. 2026-11-18
        "description": {"type": "doc", "version": 1, "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": description}]}]},
    }})
    key = issue["key"]

    # 5. Move it to its status (new tickets start in "To Do")
    if row["status"] in STATUS_NAMES:
        transitions = jira("GET", f"/rest/api/3/issue/{key}/transitions")["transitions"]
        target = next(t for t in transitions if t["to"]["name"] in STATUS_NAMES[row["status"]])
        jira("POST", f"/rest/api/3/issue/{key}/transitions", json={"transition": {"id": target["id"]}})

    print(f"{row['id']} -> {key} ({row['status']}, {row['priority']})")

print("Done.")