import json
import os

import pathlib
brain_dir = os.environ.get("ANTIGRAVITY_BRAIN_DIR")
if brain_dir:
    log_path = os.path.join(brain_dir, ".system_generated", "logs", "transcript.jsonl")
else:
    project_root = pathlib.Path(__file__).parent.parent.resolve()
    log_path = os.path.join(project_root, "artifacts", "transcript.jsonl")

with open(log_path, "r", encoding="utf-8") as f:
    for line in f:
        data = json.loads(line)
        if data.get("source") == "USER_EXPLICIT":
            print(f"Step {data.get('step_index')}:")
            print(data.get("content"))
            print("=" * 60)
