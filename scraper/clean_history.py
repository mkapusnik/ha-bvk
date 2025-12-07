import json
import os

DATA_DIR = "/app/data"
HISTORY_PATH = os.path.join(DATA_DIR, "history.json")

if os.path.exists(HISTORY_PATH):
    with open(HISTORY_PATH, 'r') as f:
        data = json.load(f)
    
    if data:
        print(f"Removing last entry: {data[-1]}")
        data.pop()
        
    with open(HISTORY_PATH, 'w') as f:
        json.dump(data, f, indent=2)
    print("Cleaned history.json")
else:
    print("history.json not found")
