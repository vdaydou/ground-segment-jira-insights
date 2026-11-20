"""Process indicators (KPIs) computed from the ticket table built by jira_data.py."""
import pandas as pd

STEPS = {  # name of the step: (date it starts, date it ends)
    "Waiting (To Do)": ("created", "in_progress"),
    "Work (In Progress)": ("in_progress", "in_review"),
    "Review (In Review)": ("in_review", "done"),
}
STUCK_AFTER_DAYS = 10  # an open ticket older than this in its current step is flagged
PRIORITY_ORDER = ["Highest", "High", "Medium", "Low"]


def days_between(start, end):
    """Duration in days between two date columns (empty if one date is missing)."""
    return (end - start).dt.total_seconds() / 86400


def add_durations(tickets, now=None):
    """Add duration columns (in days) to the ticket table."""
    now = now or pd.Timestamp.now()
    t = tickets.copy()
    t["lead_time"] = days_between(t["created"], t["done"])  # from creation to closure
    for step, (start, end) in STEPS.items():
        t[step] = days_between(t[start], t[end])
    # How long an open ticket has been in its current step
    current_start = {"To Do": "created", "In Progress": "in_progress", "In Review": "in_review"}
    t["days_in_status"] = None
    for status, column in current_start.items():
        rows = t["status"] == status
        t.loc[rows, "days_in_status"] = days_between(t.loc[rows, column], now).clip(lower=0)
    t["days_in_status"] = t["days_in_status"].astype(float)
    return t


def headline_kpis(t, now=None):
    """The few numbers shown at the top of the dashboard."""
    now = now or pd.Timestamp.now()
    last_30_days = t["done"] >= now - pd.Timedelta(days=30)
    open_tickets = t[t["status"] != "Done"]
    return {
        "Open tickets": len(open_tickets),
        "Closed in the last 30 days": int(last_30_days.sum()),
        "Median lead time (days)": float(round(t["lead_time"].median(), 1)),
        "Stuck tickets": int((open_tickets["days_in_status"] > STUCK_AFTER_DAYS).sum()),
    }


def time_per_step(t):
    """Median and 90th percentile time spent in each step: shows where the process slows down."""
    return pd.DataFrame({
        "median (days)": t[list(STEPS)].median(),
        "90% of tickets under (days)": t[list(STEPS)].quantile(0.9),
    }).round(1)


def monthly_flow(t):
    """Tickets created and closed per month: is the backlog growing or shrinking?"""
    created = t.groupby(t["created"].dt.to_period("M")).size()
    closed = t.groupby(t["done"].dt.to_period("M")).size()
    flow = pd.DataFrame({"created": created, "closed": closed}).fillna(0).astype(int)
    flow.index = flow.index.astype(str)
    return flow


def lead_time_by(t, column):
    """Median lead time and number of closed tickets, per priority or per subsystem."""
    closed = t[t["status"] == "Done"]
    result = closed.groupby(column)["lead_time"].agg(["median", "count"]).round(1)
    if column == "priority":
        result = result.reindex(PRIORITY_ORDER)  # logical order instead of alphabetical
    return result


def stuck_tickets(t):
    """Open tickets that have been in the same step for too long, oldest first."""
    stuck = t[(t["status"] != "Done") & (t["days_in_status"] > STUCK_AFTER_DAYS)]
    columns = ["id", "jira_key", "summary", "status", "priority", "days_in_status"]
    return stuck.sort_values("days_in_status", ascending=False)[columns].round(1)


if __name__ == "__main__":
    from jira_data import load_tickets

    pd.set_option("display.width", 150)
    pd.set_option("display.max_columns", None)
    tickets = add_durations(load_tickets())
    print("Headline KPIs:", headline_kpis(tickets), "\n")
    print("Time spent in each step:\n", time_per_step(tickets), "\n")
    print("Monthly flow:\n", monthly_flow(tickets), "\n")
    print("Lead time by priority:\n", lead_time_by(tickets, "priority"), "\n")
    print("Stuck tickets:\n", stuck_tickets(tickets))