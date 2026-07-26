import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

import pathlib
import os
brain_dir = os.environ.get("ANTIGRAVITY_BRAIN_DIR")
if brain_dir:
    log_path = os.path.join(brain_dir, ".system_generated", "logs", "transcript.jsonl")
else:
    project_root = pathlib.Path(__file__).parent.parent.resolve()
    log_path = os.path.join(project_root, "artifacts", "transcript.jsonl")

with open(log_path, "r", encoding="utf-8") as f:
    lines = [json.loads(line) for line in f]

out = []
for x in lines:
    source = x.get("source")
    step_type = x.get("type")
    content = x.get("content", "")
    step_idx = x.get("step_index")
    tool_calls = x.get("tool_calls")
    
    # Check if this step has any attachments or media files
    is_user = source in ("USER_EXPLICIT", "USER")
    has_media = "media__" in content or "media_14be85a5" in content or ".png" in content
    if tool_calls:
        has_media = has_media or any("media__" in str(tc) or "media_14be85a5" in str(tc) or ".png" in str(tc) for tc in tool_calls)
        
    if is_user or has_media:
        out.append(f"Step {step_idx} | Source: {source} | Type: {step_type}")
        out.append(f"Content: {content}")
        if tool_calls:
            out.append(f"Tool Calls: {json.dumps(tool_calls)}")
        out.append("-" * 60)

project_root = pathlib.Path(__file__).parent.parent.resolve()
matches_path = os.path.join(project_root, "scratch", "matches.txt")
with open(matches_path, "w", encoding="utf-8") as f_out:
    f_out.write("\n".join(out))

print(f"Wrote matches to {matches_path}")
