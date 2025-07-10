import json
import os

MESSAGES_FILE = "participant_data/messages.json"

try:
    with open(MESSAGES_FILE, "r") as f:
        MESSAGES = json.load(f)
except FileNotFoundError:
    MESSAGES = []

def save_messages():
    with open(MESSAGES_FILE, "w") as f:
        json.dump(MESSAGES, f, indent=4)