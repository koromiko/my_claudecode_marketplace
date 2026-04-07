---
description: Generate a visual timeline chronicle of the current Claude Code session, then run a retrospective
allowed-tools: Bash(python3:*), Bash(open:*), Bash(ls:*), Bash(head:*), Read, Skill
---

# Session Chronicle

Generate a vertical timeline HTML view of the current conversation showing tool durations, token usage, and bottlenecks. Then run a retrospective for improvement analysis and memory updates.

## Step 1: Locate the Current Session JSONL

Determine the session file path:

1. The current working directory is the project root. Encode it to the Claude projects path format:
   - Take the absolute path (e.g., `/Users/sthuang/Project/myapp`)
   - Replace each `/` with `-` and strip the leading `-` (e.g., `Users-sthuang-Project-myapp`)
   - The session directory is `~/.claude/projects/{encoded_path}/`

2. Find the most recently modified JSONL file (this is likely the current session):

```bash
ls -t ~/.claude/projects/{encoded_path}/*.jsonl | head -1
```

3. Confirm it's the active session by reading the first few messages:

```bash
head -20 <path> | python3 -c "
import sys, json
for line in sys.stdin:
    try:
        d = json.loads(line.strip())
        if d.get('sessionId'):
            print('Session:', d['sessionId'])
            break
    except: pass
"
```

Note the session ID for use in the output filename.

## Step 2: Generate the Chronicle HTML

Run the generator script. The `--project` flag is the human-readable project name (decode the directory name by replacing `-` with `/`).

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate_chronicle.py \
  --input <session_jsonl_path> \
  --output /tmp/chronicle_<session_id_first_8_chars>.html \
  --project "<project_name>"
```

If the script fails, read the error output and troubleshoot. Common issues:
- File not found: double-check the encoded path
- No messages: the session file may be too new (still being written); retry

## Step 3: Open in Browser

```bash
open /tmp/chronicle_<session_id_first_8_chars>.html
```

Tell the user the chronicle is open in their browser and give a brief summary of what it shows:
- Total session duration
- Number of tool calls and turns
- The top 3 slowest operations
- Notable features used (skills, MCP tools, agents)

## Step 4: Run Retrospective

Hand off to the retrospective skill for session summary, improvement analysis, and memory/CLAUDE.md/rules update opportunities:

Invoke `/workflow:retrospective`
