import json
import os

log_path = r"C:\Users\abraa\.gemini\antigravity\brain\14be85a5-d9ba-430e-b431-2cc4a11c614e\.system_generated\logs\transcript.jsonl"

with open(log_path, "r", encoding="utf-8") as f:
    for line in f:
        data = json.loads(line)
        if data.get("source") == "USER_EXPLICIT":
            print(f"Step {data.get('step_index')}:")
            print(data.get("content"))
            print("=" * 60)
