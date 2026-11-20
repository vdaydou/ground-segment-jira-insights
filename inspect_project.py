"""Print how the Jira project is configured: issue types, statuses and fields."""
import os

import requests
from dotenv import load_dotenv

load_dotenv()
JIRA_URL = os.getenv("JIRA_URL")
AUTH = (os.getenv("JIRA_EMAIL"), os.getenv("JIRA_API_TOKEN"))
PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY")


def get(path):
    """Send a GET request to the Jira API and return the JSON answer."""
    response = requests.get(f"{JIRA_URL}{path}", auth=AUTH, timeout=30)
    response.raise_for_status()
    return response.json()


# 1. Issue types and the statuses each one can take
for issue_type in get(f"/rest/api/3/project/{PROJECT_KEY}/statuses"):
    statuses = [s["name"] for s in issue_type["statuses"]]
    print(f"Issue type: {issue_type['name']} (id {issue_type['id']})")
    print("   statuses:", statuses)

# 2. Fields that can be filled when creating each issue type
types = get(f"/rest/api/3/issue/createmeta/{PROJECT_KEY}/issuetypes")
for issue_type in types["issueTypes"]:
    fields = get(f"/rest/api/3/issue/createmeta/{PROJECT_KEY}/issuetypes/{issue_type['id']}")
    names = [f["name"] for f in fields["fields"]]
    print(f"Fields for {issue_type['name']}:", names)