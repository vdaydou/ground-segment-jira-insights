"""Weekly summary of the ticket situation, written by a Large Language Model (Google Gemini).

The model only receives figures computed by metrics.py and the list of open tickets,
and is told to use nothing else: the numbers come from the code, the wording from the AI.
"""
import os

import pandas as pd
import requests
from dotenv import load_dotenv

from metrics import headline_kpis, stuck_tickets, time_per_step

load_dotenv()
MODEL = "gemini-flash-lite-latest"  # free tier, fast and light: enough for a short summary
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

INSTRUCTIONS = """You are an assistant for the engineering team of a satellite ground segment.
Write the weekly status summary of the team's Jira tickets, for the team lead.
Rules:
- Use ONLY the data given below. Never invent a ticket, a number or a cause.
- Write in plain, factual British English, in Markdown, under 250 words.
- Use exactly these sections: "## Overview", "## Bottleneck", "## Tickets needing attention",
  "## Suggested actions" (2 or 3 concrete actions, each linked to a figure from the data).
- Quote ticket ids (e.g. GSO-4) when you mention a ticket."""


def build_prompt(tickets, now=None):
    """Turn the ticket table into a short text report that the model can read."""
    now = now or pd.Timestamp.now()
    week_ago = now - pd.Timedelta(days=7)
    open_tickets = tickets[tickets["status"] != "Done"].sort_values("days_in_status", ascending=False)
    columns = ["jira_key", "summary", "subsystem", "priority", "status", "days_in_status"]
    return "\n\n".join([
        f"Date: {now:%d %B %Y}",
        f"Headline indicators: {headline_kpis(tickets, now)}",
        f"Tickets created in the last 7 days: {int((tickets['created'] >= week_ago).sum())}",
        f"Tickets closed in the last 7 days: {int((tickets['done'] >= week_ago).sum())}",
        "Time spent in each workflow step (days):\n" + time_per_step(tickets).to_string(),
        "Stuck tickets (more than 10 days in the same step):\n"
        + (stuck_tickets(tickets).to_string(index=False) if len(stuck_tickets(tickets)) else "none"),
        "All open tickets:\n" + open_tickets[columns].round(1).to_string(index=False),
    ])


def ask_llm(prompt):
    """Send the instructions and the data to the Gemini API and return the answer text."""
    response = requests.post(
        GEMINI_URL,
        headers={"x-goog-api-key": os.getenv("GEMINI_API_KEY")},
        json={
            "system_instruction": {"parts": [{"text": INSTRUCTIONS}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2,        # low = factual and stable
            "maxOutputTokens": 2048},  # enough room for the whole summary
        },
        timeout=120,
    )
    response.raise_for_status()
    candidate = response.json()["candidates"][0]
    # Gemini may split its answer into several parts: join them all
    text = "".join(part.get("text", "") for part in candidate["content"]["parts"])
    if candidate.get("finishReason") not in (None, "STOP"):
        text += f"\n\n*(The model stopped early: {candidate['finishReason']}.)*"
    return text


def weekly_summary(tickets):
    return ask_llm(build_prompt(tickets))

if __name__ == "__main__":
    from jira_data import load_tickets
    from metrics import add_durations

    tickets = add_durations(load_tickets())
    print("----- Data sent to the model -----\n" + build_prompt(tickets))
    print("\n----- Summary written by the model -----\n" + weekly_summary(tickets))