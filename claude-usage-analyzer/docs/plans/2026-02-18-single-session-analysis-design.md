# Single-Session Deep-Dive Analysis Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `--session <uuid>` support to `/analyze-usage` that produces a deep-dive report for a single session.

**Architecture:** New `--session` flag on `generate_report.py` to find and extract enriched session data, plus a new `analyze_single_session.py` script for deep-dive analysis. The command definition gains a conditional branch for single-session mode.

**Tech Stack:** Python 3.8+ standard library only (json, argparse, re, datetime, pathlib, collections)

---

### Task 1: Add `find_session_file()` and `generate_deep_dive_data()` to `generate_report.py`

**Files:**
- Modify: `scripts/generate_report.py`

**Step 1: Add `find_session_file()` function after the existing `_get_session_file_path()` function (after line 127)**

```python
def find_session_file(session_id: str, claude_dir: str = None) -> Optional[Dict]:
    """Search all project directories for a session file by UUID.

    Args:
        session_id: The full session UUID
        claude_dir: Optional override for ~/.claude directory

    Returns:
        Dict with file_path, project_name, session_id, modified_time or None if not found
    """
    projects_dir = Path(claude_dir or os.path.expanduser("~/.claude")) / "projects"
    if not projects_dir.exists():
        return None

    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue
        session_file = project_dir / f"{session_id}.jsonl"
        if session_file.exists():
            project_name = project_dir.name.replace("-", "/")
            return {
                "file_path": session_file,
                "project_name": project_name,
                "session_id": session_id,
                "modified_time": datetime.fromtimestamp(session_file.stat().st_mtime)
            }
    return None
```

**Step 2: Add `extract_tool_call_timeline()` function after `find_session_file()`**

```python
def extract_tool_call_timeline(session_data: Dict) -> List[Dict]:
    """Extract an ordered timeline of all tool calls from a session.

    Args:
        session_data: Parsed session data from SessionExtractor.parse_session()

    Returns:
        List of tool call dicts with name, key_input, timestamp, index
    """
    timeline = []
    index = 0

    for msg in session_data.get("messages", []):
        if msg.get("type") != "assistant":
            continue
        content = msg.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            tool_name = block.get("name", "unknown")
            tool_input = block.get("input", {})

            # Extract the most relevant input field for each tool type
            key_input = ""
            if tool_name in ("Read", "Edit", "Write"):
                key_input = tool_input.get("file_path", "")
            elif tool_name == "Bash":
                cmd = tool_input.get("command", "")
                key_input = cmd[:200]
            elif tool_name == "Grep":
                key_input = f"pattern='{tool_input.get('pattern', '')}'"
            elif tool_name == "Glob":
                key_input = f"pattern='{tool_input.get('pattern', '')}'"
            elif tool_name == "Skill":
                key_input = tool_input.get("skill", "")
            elif tool_name == "Task":
                key_input = tool_input.get("description", "")
            elif tool_name == "WebSearch":
                key_input = tool_input.get("query", "")
            elif tool_name == "WebFetch":
                key_input = tool_input.get("url", "")
            else:
                # Generic: take the first string value from input
                for v in tool_input.values():
                    if isinstance(v, str) and v:
                        key_input = v[:100]
                        break

            timeline.append({
                "index": index,
                "tool": tool_name,
                "key_input": key_input,
                "timestamp": msg.get("timestamp"),
            })
            index += 1

    return timeline


def extract_conversation_flow(session_data: Dict) -> Dict:
    """Extract key conversation moments for deep-dive analysis.

    Returns a structured summary of the conversation flow:
    - initial_prompts: First 3 user messages (full text, up to 1000 chars each)
    - decision_points: User messages that redirect or refine the task
    - errors: Messages containing error indicators
    - final_messages: Last 2 user and assistant messages
    """
    user_prompts = session_data.get("user_prompts", [])
    assistant_responses = session_data.get("assistant_responses", [])

    # Initial prompts (up to first 3, full text)
    initial_prompts = []
    for p in user_prompts[:3]:
        content = p.get("content", "")
        initial_prompts.append({
            "content": content[:1000],
            "timestamp": p.get("timestamp"),
        })

    # Decision points: messages that change direction (keywords)
    redirect_keywords = [
        "instead", "actually", "wait", "change", "no,", "don't",
        "different", "let's try", "go back", "scratch that"
    ]
    decision_points = []
    for p in user_prompts[1:]:  # Skip first prompt
        content = p.get("content", "")
        if any(kw in content.lower() for kw in redirect_keywords):
            decision_points.append({
                "content": content[:500],
                "timestamp": p.get("timestamp"),
            })

    # Error mentions in assistant responses
    error_patterns = ["error", "failed", "exception", "cannot", "unable"]
    errors = []
    for r in assistant_responses:
        content = r.get("content", "")
        if any(ep in content.lower() for ep in error_patterns):
            errors.append({
                "content": content[:500],
                "timestamp": r.get("timestamp"),
            })

    # Final messages
    final_user = []
    for p in user_prompts[-2:]:
        final_user.append({
            "content": p.get("content", "")[:500],
            "timestamp": p.get("timestamp"),
        })

    final_assistant = []
    for r in assistant_responses[-2:]:
        final_assistant.append({
            "content": r.get("content", "")[:500],
            "timestamp": r.get("timestamp"),
        })

    return {
        "initial_prompts": initial_prompts,
        "decision_points": decision_points[:5],
        "errors": errors[:10],
        "final_user_messages": final_user,
        "final_assistant_messages": final_assistant,
    }


def extract_file_operations(session_data: Dict) -> Dict:
    """Group file operations by type (read, edit, write).

    Returns dict with keys: reads, edits, writes — each a list of file paths.
    """
    reads = []
    edits = []
    writes = []

    for msg in session_data.get("messages", []):
        if msg.get("type") != "assistant":
            continue
        content = msg.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            tool_name = block.get("name", "")
            file_path = block.get("input", {}).get("file_path", "")
            if not file_path:
                continue
            if tool_name == "Read":
                reads.append(file_path)
            elif tool_name == "Edit":
                edits.append(file_path)
            elif tool_name == "Write":
                writes.append(file_path)

    # Deduplicate while preserving order
    def unique_ordered(items):
        seen = set()
        result = []
        for item in items:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result

    return {
        "reads": unique_ordered(reads),
        "edits": unique_ordered(edits),
        "writes": unique_ordered(writes),
        "total_read_ops": len(reads),
        "total_edit_ops": len(edits),
        "total_write_ops": len(writes),
    }


def extract_bash_commands(session_data: Dict) -> List[Dict]:
    """Extract all bash commands with error detection.

    Returns list of dicts with command text, has_error flag, and timestamp.
    """
    commands = []
    error_patterns = [
        r'\berror\b', r'\bfailed\b', r'\bfailure\b', r'\bexception\b',
        r'\bnot found\b', r'\bcommand not found\b', r'\bpermission denied\b'
    ]

    for msg in session_data.get("messages", []):
        if msg.get("type") != "assistant":
            continue
        content = msg.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            if block.get("name") != "Bash":
                continue
            cmd = block.get("input", {}).get("command", "")
            if not cmd:
                continue

            has_error = any(
                re.search(pat, cmd.lower())
                for pat in error_patterns
            )

            commands.append({
                "command": cmd[:500],
                "has_error_pattern": has_error,
                "timestamp": msg.get("timestamp"),
            })

    return commands


def generate_deep_dive_data(session_data: Dict, analyzed: Dict) -> Dict:
    """Generate enriched deep-dive data for a single session.

    Combines standard condensed session data with additional timeline,
    conversation flow, and detailed operation data.

    Args:
        session_data: Full parsed session from SessionExtractor
        analyzed: Result from analyze_session_for_report()

    Returns:
        Dict with all deep-dive data fields
    """
    # Get the standard condensed session data
    condensed = condense_session_for_report(session_data, analyzed)

    # Extract enriched data from the full session
    tool_timeline = extract_tool_call_timeline(session_data)
    conversation_flow = extract_conversation_flow(session_data)
    file_ops = extract_file_operations(session_data)
    bash_cmds = extract_bash_commands(session_data)

    # Classify git operations from bash commands
    all_commands = [c["command"] for c in bash_cmds]
    git_ops = classify_git_operations(all_commands)

    # Get completion analysis details
    completion = analyzed.get("completion_analysis", {})

    return {
        **condensed,
        "deep_dive": {
            "tool_call_timeline": tool_timeline,
            "conversation_flow": conversation_flow,
            "file_operations": file_ops,
            "bash_commands": bash_cmds,
            "git_operations": {
                "has_commit": git_ops.get("has_commit", False),
                "has_push": git_ops.get("has_push", False),
                "has_failed_commit": git_ops.get("has_failed_commit", False),
                "commit_count": git_ops.get("commit_count", 0),
                "git_commands": git_ops.get("git_commands", []),
            },
            "completion_details": {
                "confidence_score": completion.get("confidence_score"),
                "confidence_assessment": completion.get("confidence_assessment"),
                "positive_signals": completion.get("positive_signals", []),
                "negative_signals": completion.get("negative_signals", []),
                "criteria_met": completion.get("criteria_met", []),
                "criteria_missing": completion.get("criteria_missing", []),
                "failure_signals": completion.get("failure_signals", []),
            },
            "all_user_prompts": [
                {"content": p.get("content", "")[:500], "timestamp": p.get("timestamp")}
                for p in session_data.get("user_prompts", [])
            ],
        },
    }
```

**Step 3: Add `--session` argument to the argparse in `main()` (after the `--project` argument, around line 485)**

Add this after the existing `--project` argument block:

```python
    parser.add_argument(
        "--session",
        type=str,
        help="Analyze a single session by its full UUID"
    )
```

**Step 4: Add single-session handling at the start of `main()`, after `args = parser.parse_args()` (line 492)**

Insert this block right after the date validation check (after line 496):

```python
    # Handle single session mode
    if args.session:
        session_id = args.session.strip()
        print(f"Looking for session: {session_id}...")

        session_info = find_session_file(session_id)
        if not session_info:
            print(f"Error: Session '{session_id}' not found in ~/.claude/projects/")
            print("Make sure you're using the full UUID (e.g., 1baea1cc-ad12-472d-806b-cf9455a101df)")
            return

        print(f"Found session in project: {session_info['project_name']}")

        # Parse the session
        extractor = SessionExtractor()
        session_data = extractor.parse_session(session_info)
        summary = generate_summary_for_analysis(session_data, include_messages=False)

        # Analyze the session
        analyzed = analyze_session_for_report(summary)

        # Generate deep-dive data (uses full session_data for enriched extraction)
        deep_dive = generate_deep_dive_data(session_data, analyzed)

        # Build output structure
        output_data = {
            "report_metadata": {
                "generated_at": datetime.now().isoformat(),
                "mode": "single_session",
                "session_id": session_id,
            },
            "session": deep_dive,
        }

        # Save to file
        output_dir = Path(args.output_dir)
        data_dir = output_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        output_path = data_dir / f"session_deep_dive_{session_id[:8]}.json"

        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2, default=str)

        print(f"\nDeep-dive data saved to: {output_path}")
        print(f"Session: {deep_dive.get('session_id_short', session_id[:8])}")
        print(f"Project: {deep_dive.get('project', 'unknown')}")
        print(f"Duration: {deep_dive.get('duration_minutes', 0)} minutes")
        print(f"Task Type: {deep_dive.get('task_type', 'unknown')}")
        print(f"Outcome: {deep_dive.get('outcome', 'unknown')}")
        print(f"Tool Calls: {len(deep_dive.get('deep_dive', {}).get('tool_call_timeline', []))}")
        return
```

**Step 5: Run a quick validation**

```bash
cd /Users/sthuang/Project/cc_plugin_marketplace/plugins/claude-usage-analyzer && python3 scripts/generate_report.py --session nonexistent-uuid
```

Expected: "Error: Session 'nonexistent-uuid' not found in ~/.claude/projects/"

**Step 6: Test with a real session ID**

```bash
cd /Users/sthuang/Project/cc_plugin_marketplace/plugins/claude-usage-analyzer && ls ~/.claude/projects/$(ls ~/.claude/projects/ | head -1)/*.jsonl | head -1 | xargs -I{} basename {} .jsonl | xargs -I{} python3 scripts/generate_report.py --session {}
```

Expected: Successful output showing session details and a `session_deep_dive_*.json` file in `reports/data/`.

**Step 7: Commit**

```bash
git add scripts/generate_report.py
git commit -m "feat: add --session flag to generate_report.py for single-session deep-dive extraction"
```

---

### Task 2: Create `analyze_single_session.py`

**Files:**
- Create: `scripts/analyze_single_session.py`

**Step 1: Create the analysis script**

```python
#!/usr/bin/env python3
"""
Single Session Deep-Dive Analyzer

Takes the deep-dive session data from generate_report.py --session
and produces a structured analysis optimized for Claude to generate
a deep-dive markdown report.

Usage:
    python analyze_single_session.py --input session_deep_dive_*.json --output session_analysis_*.json
"""

import json
import re
import argparse
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict
from typing import Dict, List, Any


def analyze_tool_usage(timeline: List[Dict]) -> Dict:
    """Analyze tool usage patterns from the timeline.

    Returns:
        Dict with tool counts, sequences, and pattern analysis
    """
    if not timeline:
        return {"total_calls": 0, "by_tool": {}, "sequences": [], "patterns": []}

    # Count by tool
    tool_counts = Counter(t["tool"] for t in timeline)

    # Detect sequences (consecutive same-tool or common patterns)
    sequences = []
    current_seq = []
    for t in timeline:
        if current_seq and current_seq[-1]["tool"] == t["tool"]:
            current_seq.append(t)
        else:
            if len(current_seq) >= 3:
                sequences.append({
                    "tool": current_seq[0]["tool"],
                    "count": len(current_seq),
                    "start_index": current_seq[0]["index"],
                })
            current_seq = [t]
    if len(current_seq) >= 3:
        sequences.append({
            "tool": current_seq[0]["tool"],
            "count": len(current_seq),
            "start_index": current_seq[0]["index"],
        })

    # Detect common workflow patterns
    patterns = []
    tool_names = [t["tool"] for t in timeline]

    # Read -> Edit pattern (exploration then modification)
    read_edit_count = sum(
        1 for i in range(len(tool_names) - 1)
        if tool_names[i] == "Read" and tool_names[i+1] == "Edit"
    )
    if read_edit_count > 0:
        patterns.append({"pattern": "Read -> Edit", "count": read_edit_count, "description": "Explore then modify"})

    # Edit -> Bash pattern (modify then test/run)
    edit_bash_count = sum(
        1 for i in range(len(tool_names) - 1)
        if tool_names[i] in ("Edit", "Write") and tool_names[i+1] == "Bash"
    )
    if edit_bash_count > 0:
        patterns.append({"pattern": "Edit -> Bash", "count": edit_bash_count, "description": "Modify then run/test"})

    # Grep/Glob -> Read pattern (search then examine)
    search_read_count = sum(
        1 for i in range(len(tool_names) - 1)
        if tool_names[i] in ("Grep", "Glob") and tool_names[i+1] == "Read"
    )
    if search_read_count > 0:
        patterns.append({"pattern": "Search -> Read", "count": search_read_count, "description": "Find then examine"})

    return {
        "total_calls": len(timeline),
        "by_tool": dict(tool_counts.most_common()),
        "repeated_sequences": sequences,
        "workflow_patterns": sorted(patterns, key=lambda p: -p["count"]),
    }


def analyze_conversation(flow: Dict, all_prompts: List[Dict]) -> Dict:
    """Analyze conversation dynamics.

    Returns metrics about conversation flow, engagement, and direction changes.
    """
    total_prompts = len(all_prompts)
    decision_points = flow.get("decision_points", [])
    errors = flow.get("errors", [])

    # Calculate average prompt length
    prompt_lengths = [len(p.get("content", "")) for p in all_prompts]
    avg_length = round(sum(prompt_lengths) / len(prompt_lengths), 0) if prompt_lengths else 0

    return {
        "total_user_messages": total_prompts,
        "avg_prompt_length_chars": avg_length,
        "direction_changes": len(decision_points),
        "error_mentions_in_responses": len(errors),
        "decision_points_summary": [
            dp.get("content", "")[:200] for dp in decision_points[:3]
        ],
    }


def analyze_file_impact(file_ops: Dict) -> Dict:
    """Analyze the impact of file operations.

    Returns summary of file operations with unique files and operation counts.
    """
    reads = file_ops.get("reads", [])
    edits = file_ops.get("edits", [])
    writes = file_ops.get("writes", [])

    all_files = set(reads + edits + writes)
    modified_files = set(edits + writes)

    return {
        "total_unique_files": len(all_files),
        "files_read_only": len(set(reads) - modified_files),
        "files_edited": len(set(edits)),
        "files_created": len(set(writes) - set(edits)),
        "total_read_ops": file_ops.get("total_read_ops", 0),
        "total_edit_ops": file_ops.get("total_edit_ops", 0),
        "total_write_ops": file_ops.get("total_write_ops", 0),
        "modified_files": sorted(modified_files),
        "read_only_files": sorted(set(reads) - modified_files),
    }


def detect_workflow_phase(timeline: List[Dict]) -> List[Dict]:
    """Detect workflow phases from the tool call timeline.

    Identifies phases like: exploration, implementation, testing, cleanup.
    """
    if not timeline:
        return []

    phases = []
    current_phase = None
    phase_start = 0

    for i, t in enumerate(timeline):
        tool = t["tool"]

        # Determine the phase for this tool call
        if tool in ("Grep", "Glob", "Read", "WebSearch", "WebFetch"):
            phase = "exploration"
        elif tool in ("Edit", "Write", "NotebookEdit"):
            phase = "implementation"
        elif tool == "Bash":
            cmd = t.get("key_input", "").lower()
            if any(kw in cmd for kw in ["test", "pytest", "jest", "npm test"]):
                phase = "testing"
            elif any(kw in cmd for kw in ["git commit", "git push", "git add"]):
                phase = "git_operations"
            else:
                phase = "execution"
        elif tool == "Task":
            phase = "delegation"
        elif tool == "Skill":
            phase = "skill_invocation"
        else:
            phase = "other"

        if phase != current_phase:
            if current_phase is not None:
                phases.append({
                    "phase": current_phase,
                    "start_index": phase_start,
                    "end_index": i - 1,
                    "tool_count": i - phase_start,
                })
            current_phase = phase
            phase_start = i

    # Close last phase
    if current_phase is not None:
        phases.append({
            "phase": current_phase,
            "start_index": phase_start,
            "end_index": len(timeline) - 1,
            "tool_count": len(timeline) - phase_start,
        })

    return phases


def analyze_single_session(data: Dict) -> Dict:
    """Run full deep-dive analysis on a single session.

    Args:
        data: The output from generate_report.py --session
              (has report_metadata and session keys)

    Returns:
        Structured analysis dict for Claude to use in report generation
    """
    session = data.get("session", {})
    deep_dive = session.get("deep_dive", {})

    # Core session info
    session_info = {
        "session_id": session.get("session_id", ""),
        "session_id_short": session.get("session_id_short", ""),
        "project": session.get("project", ""),
        "full_project_path": session.get("full_project_path", ""),
        "date": session.get("date", ""),
        "duration_minutes": session.get("duration_minutes", 0),
        "git_branch": session.get("git_branch"),
        "task_type": session.get("task_type", "unknown"),
        "task_summary": session.get("task_summary", ""),
        "outcome": session.get("outcome", "unknown"),
        "completion_confidence": session.get("completion_confidence"),
        "confidence_assessment": session.get("confidence_assessment"),
    }

    # Tool usage analysis
    tool_analysis = analyze_tool_usage(deep_dive.get("tool_call_timeline", []))

    # Conversation analysis
    conversation_analysis = analyze_conversation(
        deep_dive.get("conversation_flow", {}),
        deep_dive.get("all_user_prompts", []),
    )

    # File impact analysis
    file_impact = analyze_file_impact(deep_dive.get("file_operations", {}))

    # Workflow phases
    workflow_phases = detect_workflow_phase(deep_dive.get("tool_call_timeline", []))

    # Completion details (pass through from deep dive)
    completion_details = deep_dive.get("completion_details", {})

    # Git operations summary
    git_ops = deep_dive.get("git_operations", {})

    # Bash command analysis
    bash_cmds = deep_dive.get("bash_commands", [])
    error_commands = [c for c in bash_cmds if c.get("has_error_pattern")]

    # Success and issue evidence
    successes = session.get("successes", [])
    issues = session.get("issues", [])

    return {
        "analysis_metadata": {
            "generated_at": datetime.now().isoformat(),
            "analysis_type": "single_session_deep_dive",
        },
        "session_info": session_info,
        "tool_analysis": tool_analysis,
        "conversation_analysis": conversation_analysis,
        "file_impact": file_impact,
        "workflow_phases": workflow_phases,
        "completion_details": completion_details,
        "git_operations": git_ops,
        "bash_summary": {
            "total_commands": len(bash_cmds),
            "commands_with_errors": len(error_commands),
            "error_commands": [c["command"][:200] for c in error_commands[:5]],
        },
        "successes": successes,
        "issues": issues,
        # Include raw deep-dive data for Claude's reference
        "conversation_flow": deep_dive.get("conversation_flow", {}),
        "tool_call_timeline": deep_dive.get("tool_call_timeline", []),
        "all_user_prompts": deep_dive.get("all_user_prompts", []),
    }


def print_summary(analysis: Dict):
    """Print a quick summary of the analysis."""
    info = analysis["session_info"]
    tools = analysis["tool_analysis"]
    files = analysis["file_impact"]
    conv = analysis["conversation_analysis"]

    print("\n" + "=" * 50)
    print("SINGLE SESSION ANALYSIS")
    print("=" * 50)
    print(f"Session: {info['session_id_short']}")
    print(f"Project: {info['project']}")
    print(f"Date: {info['date']}")
    print(f"Duration: {info['duration_minutes']} minutes")
    print(f"Task Type: {info['task_type']}")
    print(f"Outcome: {info['outcome']}")
    print(f"Confidence: {info.get('completion_confidence', 'N/A')}")
    print("-" * 50)
    print(f"Tool Calls: {tools['total_calls']}")
    print(f"User Messages: {conv['total_user_messages']}")
    print(f"Files Touched: {files['total_unique_files']}")
    print(f"Files Modified: {len(files['modified_files'])}")
    print(f"Direction Changes: {conv['direction_changes']}")
    print(f"Workflow Phases: {len(analysis['workflow_phases'])}")
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze a single Claude Code session in depth",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python analyze_single_session.py --input reports/data/session_deep_dive_1baea1cc.json
    python analyze_single_session.py --input reports/data/session_deep_dive_1baea1cc.json --output my_analysis.json
        """
    )
    parser.add_argument(
        "--input", "-i",
        type=str,
        required=True,
        help="Input session deep-dive JSON file"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Output analysis JSON file (default: session_analysis_{uuid_short}.json)"
    )

    args = parser.parse_args()

    # Load deep-dive data
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        return

    print(f"Loading deep-dive data from: {input_path}")
    with open(input_path, 'r') as f:
        data = json.load(f)

    # Run analysis
    print("Analyzing session...")
    analysis = analyze_single_session(data)

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        session_id_short = analysis["session_info"]["session_id_short"]
        output_path = Path(f"session_analysis_{session_id_short}.json")

    # Save analysis
    with open(output_path, 'w') as f:
        json.dump(analysis, f, indent=2, default=str)

    print(f"Analysis saved to: {output_path}")

    # Print summary
    print_summary(analysis)


if __name__ == "__main__":
    main()
```

**Step 2: Run a basic validation (requires Task 1 to be complete)**

```bash
cd /Users/sthuang/Project/cc_plugin_marketplace/plugins/claude-usage-analyzer && python3 -c "import scripts.analyze_single_session; print('Import OK')"
```

Expected: "Import OK" (no syntax errors)

**Step 3: Commit**

```bash
git add scripts/analyze_single_session.py
git commit -m "feat: add analyze_single_session.py for single-session deep-dive analysis"
```

---

### Task 3: Update `commands/analyze-usage.md` with `--session` execution path

**Files:**
- Modify: `commands/analyze-usage.md`

**Step 1: Add `--session` to the Arguments section**

After the `### Comparison (optional)` section (around line 28), add:

```markdown
### Single Session (optional)
- `--session <uuid>` - Deep-dive analysis of a single session by its full UUID (ignores period/project args)
```

**Step 2: Add examples to the Examples section**

Add to the examples list:

```markdown
- `/analyze-usage --session 1baea1cc-ad12-472d-806b-cf9455a101df` - Deep-dive analysis of a specific session
- `/analyze-usage --session 1baea1cc-ad12-472d-806b-cf9455a101df --html` - Deep-dive HTML report for a specific session
```

**Step 3: Add the single-session execution path before Step 1**

Insert a new section before `### Step 1:` (around line 43):

```markdown
## Single Session Mode

If `--session <uuid>` is present in $ARGUMENTS, follow these steps instead of the standard pipeline:

### Step S1: Extract Single Session Data

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate_report.py --session <uuid>
```

Note the output filename: `reports/data/session_deep_dive_{uuid_short}.json`

### Step S2: Analyze Single Session

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/analyze_single_session.py --input <deep_dive_file> --output session_analysis_{uuid_short}.json
```

### Step S3: Generate Deep-Dive Report

Read both `reports/data/session_deep_dive_{uuid_short}.json` and `session_analysis_{uuid_short}.json`, then generate a deep-dive report.

**Data Available for Deep-Dive:**
- `tool_call_timeline`: Every tool call in order with name and key input
- `conversation_flow`: Initial prompts, direction changes, errors, final messages
- `file_operations`: Files grouped by read/edit/write
- `bash_commands`: All bash commands with error detection
- `git_operations`: Git command classification
- `completion_details`: Confidence signals and criteria analysis
- `workflow_phases`: Detected phases (exploration, implementation, testing, etc.)
- `all_user_prompts`: All user messages for context

**Deep-Dive Report Template:**

```markdown
# Session Deep-Dive: {session_id_short}

## Overview
| Field | Value |
|-------|-------|
| **Session ID** | {session_id} |
| **Project** | {project} |
| **Date** | {date} |
| **Duration** | {duration_minutes} minutes |
| **Branch** | {git_branch} |
| **Task Type** | {task_type} |
| **Outcome** | {outcome} (confidence: {completion_confidence}/100) |

## Task Summary
{Describe what the user was trying to accomplish based on initial_prompts and task_summary}

## Session Timeline
{Chronological narrative of key events using tool_call_timeline and conversation_flow:}
1. User started with: "{initial prompt}"
2. Exploration phase: {what was searched/read}
3. Implementation phase: {what was edited/written}
4. Testing/validation: {bash commands run}
5. Outcome: {how the session ended}

## Workflow Phases
{Use workflow_phases to describe the session structure}
| Phase | Tools | Description |
|-------|-------|-------------|

## Tool Usage Analysis
{Use tool_analysis data}
| Tool | Calls | Purpose |
|------|-------|---------|

**Patterns Detected:**
{List workflow_patterns from tool_analysis}

## File Impact
{Use file_impact data}
- Files modified: {list}
- Files read-only: {list}
- Total operations: {counts}

## What Went Well
{Success patterns with specific evidence from the session data}

## Issues Encountered
{Problems identified with root cause analysis referencing specific tool calls or conversation moments}

## Conversation Analysis
- Total user messages: {count}
- Direction changes: {count and descriptions}
- Average prompt length: {chars}

## Recommendations
{Specific, actionable suggestions based on this session's patterns:}
1. {Recommendation based on tool usage patterns}
2. {Recommendation based on conversation flow}
3. {Recommendation based on outcome analysis}
```

Save to: `reports/session_deep_dive_{session_id_short}.md`

Then skip the standard pipeline steps (Steps 1-5) and proceed to Deliverables.
```

**Step 4: Update the argument-hint in the frontmatter**

Change line 4 from:
```yaml
argument-hint: [period] [--project <name>]
```
to:
```yaml
argument-hint: [period] [--project <name>] [--session <uuid>]
```

**Step 5: Commit**

```bash
git add commands/analyze-usage.md
git commit -m "feat: add --session execution path to analyze-usage command"
```

---

### Task 4: Update CLAUDE.md documentation

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Add `--session` to the script pipeline documentation**

In the `## Script Pipeline` section, add a note after the numbered list item for `generate_report.py`:

```markdown
   - With `--session <uuid>`: searches for the specific session file, extracts enriched deep-dive data
   - Outputs: `reports/data/session_deep_dive_{uuid_short}.json`
```

And add a new entry for `analyze_single_session.py`:

```markdown
8. **analyze_single_session.py** - Single session deep-dive analysis
   - Takes `session_deep_dive_{uuid}.json` from generate_report.py --session
   - Produces tool usage patterns, workflow phase detection, conversation analysis, file impact
   - Outputs: `session_analysis_{uuid_short}.json`
```

**Step 2: Add CLI example to "Running Scripts Directly" section**

```markdown
# Analyze a single session by UUID
python3 scripts/generate_report.py --session 1baea1cc-ad12-472d-806b-cf9455a101df
python3 scripts/analyze_single_session.py --input reports/data/session_deep_dive_1baea1cc.json --output session_analysis_1baea1cc.json
```

**Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add single-session analysis documentation to CLAUDE.md"
```

---

### Task 5: End-to-end integration test

**Files:**
- None (test only)

**Step 1: Find a real session UUID to test with**

```bash
ls ~/.claude/projects/$(ls ~/.claude/projects/ | head -1)/*.jsonl | head -1 | xargs -I{} basename {} .jsonl
```

**Step 2: Run the full pipeline**

```bash
cd /Users/sthuang/Project/cc_plugin_marketplace/plugins/claude-usage-analyzer

# Step 1: Extract deep-dive data
python3 scripts/generate_report.py --session <UUID_FROM_STEP_1>

# Step 2: Analyze
python3 scripts/analyze_single_session.py --input reports/data/session_deep_dive_*.json --output session_analysis_test.json

# Step 3: Verify outputs
python3 -c "
import json
with open('reports/data/$(ls reports/data/session_deep_dive_*.json | head -1 | xargs basename)') as f:
    d = json.load(f)
    s = d['session']
    dd = s['deep_dive']
    print(f'Session ID: {s[\"session_id_short\"]}')
    print(f'Project: {s[\"project\"]}')
    print(f'Tool timeline entries: {len(dd[\"tool_call_timeline\"])}')
    print(f'File ops reads: {len(dd[\"file_operations\"][\"reads\"])}')
    print(f'Bash commands: {len(dd[\"bash_commands\"])}')
    print(f'User prompts: {len(dd[\"all_user_prompts\"])}')
    print('Deep-dive data: OK')

with open('session_analysis_test.json') as f:
    a = json.load(f)
    print(f'Tool patterns: {len(a[\"tool_analysis\"][\"workflow_patterns\"])}')
    print(f'Workflow phases: {len(a[\"workflow_phases\"])}')
    print(f'File impact unique: {a[\"file_impact\"][\"total_unique_files\"]}')
    print('Analysis data: OK')
"
```

Expected: All values populated, no errors.

**Step 3: Verify existing pipeline still works**

```bash
cd /Users/sthuang/Project/cc_plugin_marketplace/plugins/claude-usage-analyzer && python3 scripts/generate_report.py --period daily
```

Expected: Normal output, no regressions.

**Step 4: Clean up test artifacts**

```bash
rm -f session_analysis_test.json
```

**Step 5: Final commit with all working**

```bash
git add -A && git status
```

Review staged files, then if everything looks good:

```bash
git commit -m "feat: single-session deep-dive analysis via --session flag

Adds the ability to analyze a single Claude Code session by passing
--session <uuid> to the analyze-usage command. Produces enriched
deep-dive data including tool call timeline, conversation flow,
file operations, and workflow phase detection."
```

---

Plan complete and saved to `docs/plans/2026-02-18-single-session-analysis-design.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?