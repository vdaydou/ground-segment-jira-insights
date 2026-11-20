"""Quick check that Python can talk to the Jira Cloud API."""
import os

import requests
from dotenv import load_dotenv

load_dotenv()  # reads the secrets from the .env file

JIRA_URL = os.getenv("JIRA_URL")
AUTH = (os.getenv("JIRA_EMAIL"), os.getenv("JIRA_API_TOKEN"))
PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY")

# 1. Who am I? (checks that the token works)
me = requests.get(f"{JIRA_URL}/rest/api/3/myself", auth=AUTH, timeout=30)
me.raise_for_status()
print("Connected as:", me.json()["displayName"])

# 2. Does the project exist? (checks the project key)
project = requests.get(f"{JIRA_URL}/rest/api/3/project/{PROJECT_KEY}", auth=AUTH, timeout=30)
project.raise_for_status()
print("Project found:", project.json()["name"])