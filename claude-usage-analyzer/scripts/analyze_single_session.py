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
