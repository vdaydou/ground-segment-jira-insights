"""Generate a fictional six-month history of ground segment tickets.

Jira Cloud does not let you set the creation date of an issue through its API, so the
history (with realistic dates) is generated here and saved as a CSV file.
All data is invented: this project is not affiliated with ESA or the Galileo programme.
"""
import csv
import random
from datetime import datetime, timedelta

random.seed(42)  # same "random" data every time the script runs

N_TICKETS = 200
END = datetime(2026, 11, 20, 18, 0)  # "today" in the story
START = END - timedelta(days=180)     # six months of history

SUBSYSTEMS = ["Control Centre", "Sensor Stations", "Uplink Stations",
              "Orbit & Time Processing", "Network & Security"]
# One list of summary templates per ticket type ({s} = station number, {c} = context)
SUMMARIES = {
    "Anomaly": ["Intermittent signal loss at station {s}", "Wrong timestamps in logs after {c}",
                "Alarm not raised during {c}", "Data gap from station {s} during {c}",
                "Upload rejected at station {s}", "Processing slower than expected after {c}"],
    "Change Request": ["Add monitoring of station {s} health", "Update alarm thresholds after {c}",
                       "Automate the report produced after {c}", "Change the procedure used for {c}"],
    "Action": ["Check configuration of station {s}", "Review lessons learnt from {c}",
               "Update the operations manual for {c}", "Prepare the test plan for {c}"],
}
CONTEXT = ["the night shift", "the software update", "routine maintenance",
           "the weekly upload", "the backup switch-over"]
TYPES = {"Anomaly": 0.55, "Change Request": 0.25, "Action": 0.20}
PRIORITIES = {"Highest": 0.05, "High": 0.20, "Medium": 0.50, "Low": 0.25}
# Mean number of days spent in each workflow step, per priority.
# The review step is slower on purpose: it is the bottleneck the dashboard should reveal.
SPEED = {"Highest": 0.5, "High": 1.5, "Medium": 3.0, "Low": 6.0}
REVIEW_FACTOR = 2.0
STUCK_RATE = 0.10    # share of tickets that wait a long time in review (external input needed)
STUCK_FACTOR = 8.0
STATION_PREFIX = {"Uplink Stations": "ULS"}  # other subsystems refer to sensor stations (GSS)


def pick(weights):
    """Pick one key of a {value: probability} dictionary."""
    return random.choices(list(weights), weights=list(weights.values()))[0]


def duration(priority, factor=1.0):
    """Random duration of one workflow step: most are short, a few are very long."""
    return timedelta(days=random.expovariate(1 / (SPEED[priority] * factor)))


rows = []
for _ in range(N_TICKETS):
    ticket_type = pick(TYPES)
    subsystem = random.choice(SUBSYSTEMS)
    station = f"{STATION_PREFIX.get(subsystem, 'GSS')}-{random.randint(1, 16):02d}"
    summary = random.choice(SUMMARIES[ticket_type]).format(s=station, c=random.choice(CONTEXT))
    priority = pick(PRIORITIES)
    created = START + timedelta(seconds=random.uniform(0, (END - START).total_seconds()))

    # Move the ticket through To Do -> In Progress -> In Review -> Done, stopping at "today"
    dates = {"in_progress": None, "in_review": None, "done": None}
    status, t = "To Do", created
    review = REVIEW_FACTOR * (STUCK_FACTOR if random.random() < STUCK_RATE else 1.0)
    for next_status, key, factor in [("In Progress", "in_progress", 1.0),
                                     ("In Review", "in_review", 1.0),
                                     ("Done", "done", review)]:
        t += duration(priority, factor)
        if t > END:
            break
        dates[key], status = t, next_status

    rows.append({"summary": summary, "type": ticket_type,
                 "subsystem": subsystem, "priority": priority,
                 "status": status, "created": created, **dates})

# Number the tickets in creation order and write dates as text
rows.sort(key=lambda r: r["created"])
for i, row in enumerate(rows, start=1):
    row["id"] = f"T-{i:03d}"
    for key in ["created", "in_progress", "in_review", "done"]:
        row[key] = row[key].strftime("%Y-%m-%d %H:%M") if row[key] else ""

columns = ["id", "summary", "type", "subsystem", "priority", "status",
           "created", "in_progress", "in_review", "done"]
with open("tickets_history.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)

open_tickets = sum(r["status"] != "Done" for r in rows)
print(f"{len(rows)} tickets written to tickets_history.csv ({open_tickets} still open)")