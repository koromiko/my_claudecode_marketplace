#!/usr/bin/env python3
"""
Claude Code Usage Report Data Generator

This script extracts Claude Code sessions for a given period and generates
structured JSON data optimized for Claude Code to analyze and create reports.

Usage:
    python generate_report.py --period weekly          # Last 7 days
    python generate_report.py --period monthly         # Last 30 days
    python generate_report.py --days 14                # Custom days
    python generate_report.py --start 2025-12-01 --end 2025-12-15
    python generate_report.py --output-dir ./reports   # Custom output location
    python generate_report.py --project myapp          # Filter by project name
    python generate_report.py --period weekly --project ema  # Combine filters
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any, Optional
import argparse

# Import from existing modules
from extract_sessions import SessionExtractor, generate_summary_for_analysis
from analyze_sessions import (
    classify_task_type,
    detect_issues,
    detect_successes,
    extract_key_topics,
    generate_aggregate_report,
    analyze_session,
    classify_git_operations,
    detect_failure_signals,
    evaluate_task_completion,
    calculate_completion_confidence,
    COMPLETION_CONFIDENCE_THRESHOLD
)
from extract_global_stats import GlobalStatsExtractor


def calculate_comparison(current_stats: Dict, previous_stats: Dict) -> Dict:
    """Calculate comparison metrics between current and previous periods.

    Args:
        current_stats: Aggregate statistics for current period
        previous_stats: Aggregate statistics for previous period

    Returns:
        Dict with comparison data including deltas and percentages
    """
    def calc_delta(current: float, previous: float) -> Dict:
        """Calculate delta and percentage change."""
        delta = current - previous
        if previous > 0:
            delta_pct = round((delta / previous) * 100, 1)
        else:
            delta_pct = 100.0 if current > 0 else 0.0
        return {
            "current": current,
            "previous": previous,
            "delta": delta,
            "delta_pct": delta_pct,
            "direction": "up" if delta > 0 else ("down" if delta < 0 else "same")
        }

    current_summary = current_stats.get("summary", {})
    previous_summary = previous_stats.get("summary", {})
    current_averages = current_stats.get("averages", {})
    previous_averages = previous_stats.get("averages", {})
    current_activity = current_stats.get("activity_metrics", {})
    previous_activity = previous_stats.get("activity_metrics", {})

    return {
        "has_comparison": True,
        "sessions": calc_delta(
            current_summary.get("total_sessions", 0),
            previous_summary.get("total_sessions", 0)
        ),
        "total_duration_hours": calc_delta(
            round(current_summary.get("total_duration_minutes", 0) / 60, 1),
            round(previous_summary.get("total_duration_minutes", 0) / 60, 1)
        ),
        "avg_duration": calc_delta(
            current_averages.get("avg_duration_minutes", 0),
            previous_averages.get("avg_duration_minutes", 0)
        ),
        "total_tool_calls": calc_delta(
            current_summary.get("total_tool_calls", 0),
            previous_summary.get("total_tool_calls", 0)
        ),
        "activity_rate": calc_delta(
            current_activity.get("activity_rate", 0),
            previous_activity.get("activity_rate", 0)
        ),
        "sessions_with_edits": calc_delta(
            current_activity.get("sessions_with_edits", 0),
            previous_activity.get("sessions_with_edits", 0)
        ),
        "sessions_with_commits": calc_delta(
            current_activity.get("sessions_with_commits", 0),
            previous_activity.get("sessions_with_commits", 0)
        ),
    }


def _get_session_file_path(full_project_path: str, session_id: str) -> str:
    """Reconstruct the full path to a session's JSONL file.

    Args:
        full_project_path: The full project path (e.g., /Users/foo/bar)
        session_id: The session UUID

    Returns:
        Path to the session file (e.g., ~/.claude/projects/-Users-foo-bar/{session_id}.jsonl)
    """
    if not full_project_path or not session_id:
        return ""
    # Encode: /Users/foo/bar -> -Users-foo-bar
    encoded_path = full_project_path.replace("/", "-")
    if not encoded_path.startswith("-"):
        encoded_path = "-" + encoded_path
    return f"~/.claude/projects/{encoded_path}/{session_id}.jsonl"


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


def generate_deep_dive_data(session_data: Dict, summary: Dict, analyzed: Dict) -> Dict:
    """Generate enriched deep-dive data for a single session.

    Combines standard condensed session data with additional timeline,
    conversation flow, and detailed operation data.

    Args:
        session_data: Full parsed session from SessionExtractor.parse_session()
        summary: Output from generate_summary_for_analysis()
        analyzed: Result from analyze_session_for_report()

    Returns:
        Dict with all deep-dive data fields
    """
    # Get the standard condensed session data (uses summary format)
    condensed = condense_session_for_report(summary, analyzed)

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


def parse_date(date_str: str) -> datetime:
    """Parse a date string in YYYY-MM-DD format."""
    return datetime.strptime(date_str, "%Y-%m-%d")


def get_date_range(args) -> tuple[datetime, datetime]:
    """Determine the date range based on CLI arguments."""
    end_date = datetime.now()

    if args.start and args.end:
        start_date = parse_date(args.start)
        end_date = parse_date(args.end)
    elif args.days:
        start_date = end_date - timedelta(days=args.days)
    elif args.period == "weekly":
        start_date = end_date - timedelta(days=7)
    elif args.period == "monthly":
        start_date = end_date - timedelta(days=30)
    elif args.period == "daily":
        start_date = end_date - timedelta(days=1)
    else:
        # Default to weekly
        start_date = end_date - timedelta(days=7)

    return start_date, end_date


def calculate_days_back(start_date: datetime) -> int:
    """Calculate days back from now to the start date."""
    delta = datetime.now() - start_date
    return max(1, delta.days + 1)  # +1 to include the start day


def condense_session_for_report(session: Dict, analyzed: Dict) -> Dict:
    """
    Condense a session into the format optimized for Claude Code analysis.
    """
    # Get the primary task from initial prompts
    prompts = session.get("task_context", {}).get("initial_prompts", [])
    task_summary = ""
    for p in prompts:
        if isinstance(p, str) and len(p) > 20 and "<" not in p[:10]:
            task_summary = p[:200].replace("\n", " ").strip()
            break

    # Get outcome from analyzed data (now using expanded outcomes)
    task_analysis = analyzed.get("task_analysis", {})
    quality = analyzed.get("quality_assessment", {})
    completion_analysis = analyzed.get("completion_analysis", {})

    # Use the outcome determined by analyze_session if available
    outcome = task_analysis.get("outcome") or task_analysis.get("actual_outcome")

    # Fallback for backward compatibility if no outcome set
    if not outcome:
        if task_analysis.get("likely_completed"):
            outcome = "completed" if not quality.get("issues") else "completed_with_issues"
        elif quality.get("issues"):
            outcome = "partially_completed"
        else:
            outcome = "unclear"

    # Extract success descriptions
    successes = [s.get("description", "") for s in quality.get("successes", [])]

    # Extract issue descriptions
    issues = [i.get("description", "") for i in quality.get("issues", [])]

    # Get project short name
    project = session.get("project", "unknown")
    project_short = project.split("/")[-1] if "/" in project else project

    # Get AI-generated summary if available
    ai_summary = session.get("existing_summary", "")

    # Get sample of conversation for context
    response_samples = session.get("task_context", {}).get("response_samples", [])

    # Get Claude Code feature usage
    features = session.get("claude_code_features", {})
    skills = features.get("skills_invoked", [])
    agents = features.get("agents_spawned", [])
    slash_cmds = features.get("slash_commands", [])

    # Get full session ID and construct file path
    full_session_id = session.get("session_id", "")
    session_file_path = _get_session_file_path(project, full_session_id)

    # Get completion confidence data
    confidence_score = completion_analysis.get("confidence_score")
    confidence_assessment = completion_analysis.get("confidence_assessment")

    return {
        "session_id": full_session_id,
        "session_id_short": full_session_id[:8],
        "session_file_path": session_file_path,
        "project": project_short,
        "full_project_path": project,
        "date": (session.get("metadata", {}).get("start_time") or "")[:10] or "unknown",
        "duration_minutes": round(session.get("metadata", {}).get("duration_minutes", 0), 1),
        "git_branch": session.get("metadata", {}).get("git_branch"),
        "task_summary": task_summary,
        "task_type": task_analysis.get("task_type", "unknown"),
        "key_topics": task_analysis.get("key_topics", []),
        "outcome": outcome,
        "completion_confidence": confidence_score,
        "confidence_assessment": confidence_assessment,
        "successes": successes,
        "issues": issues,
        "ai_summary": ai_summary,
        "conversation_samples": {
            "initial_prompts": prompts[:3],
            "response_samples": response_samples[:3]
        },
        "claude_code_features": {
            "skills_invoked": [s.get("skill") if isinstance(s, dict) else s for s in skills],
            "agents_spawned": [a.get("agent_type") if isinstance(a, dict) else a for a in agents],
            "slash_commands": [c.get("command") if isinstance(c, dict) else c for c in slash_cmds]
        },
        "stats": {
            "user_messages": session.get("statistics", {}).get("user_messages", 0),
            "assistant_messages": session.get("statistics", {}).get("assistant_messages", 0),
            "tool_calls": session.get("statistics", {}).get("tool_call_count", 0),
            "tools_used": session.get("statistics", {}).get("tools_used", []),
            "files_touched": len(session.get("task_context", {}).get("files_touched", []))
        }
    }


def analyze_session_for_report(session: Dict) -> Dict:
    """Run full analysis on a session using the analyze_session function.

    This uses the enhanced completion detection including:
    - Task-type specific completion criteria
    - Failure signal detection
    - Confidence scoring
    - Expanded outcome granularity
    """
    # Use the full analyze_session function which includes all new features
    return analyze_session(session)


def generate_report_data(
    sessions: List[Dict],
    start_date: datetime,
    end_date: datetime,
    period_name: str,
    project_filter: Optional[str] = None,
    global_stats: Optional[Dict] = None,
    filtered_counts: Optional[Dict[str, int]] = None
) -> Dict:
    """
    Generate the complete report data structure optimized for Claude Code analysis.

    Args:
        sessions: List of session dictionaries
        start_date: Report period start date
        end_date: Report period end date
        period_name: Name of the period (e.g., "weekly", "monthly")
        project_filter: Optional project name filter
        global_stats: Optional global stats from ~/.claude.json
        filtered_counts: Optional dict with counts of filtered sessions:
            - empty_sessions_filtered: Sessions with no activity
            - idle_sessions_filtered: Sessions >6hr with <5 tool calls
    """
    # Analyze all sessions
    analyzed_sessions = []
    condensed_sessions = []

    for session in sessions:
        analyzed = analyze_session_for_report(session)
        analyzed_sessions.append({**session, **analyzed})
        condensed_sessions.append(condense_session_for_report(session, analyzed))

    # Generate aggregate statistics
    aggregate = generate_aggregate_report(analyzed_sessions)

    # Build the report data
    # Extract Claude Code features from aggregate
    cc_features = aggregate.get("claude_code_features", {})

    # Build metadata with filtered counts
    metadata = {
        "generated_at": datetime.now().isoformat(),
        "period": period_name,
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "total_days": (end_date - start_date).days,
        "project_filter": project_filter
    }

    # Add filtered session counts if provided
    if filtered_counts:
        if filtered_counts.get("empty_sessions_filtered", 0) > 0:
            metadata["empty_sessions_filtered"] = filtered_counts["empty_sessions_filtered"]
        if filtered_counts.get("idle_sessions_filtered", 0) > 0:
            metadata["idle_sessions_filtered"] = filtered_counts["idle_sessions_filtered"]

    report_data = {
        "report_metadata": metadata,
        "aggregate_statistics": {
            "total_sessions": aggregate["summary"]["total_sessions"],
            "total_duration_hours": round(aggregate["summary"]["total_duration_minutes"] / 60, 1),
            "total_user_messages": aggregate["summary"]["total_user_messages"],
            "total_assistant_messages": aggregate["summary"]["total_assistant_messages"],
            "total_tool_calls": aggregate["summary"]["total_tool_calls"],
            "completion_rate": aggregate.get("averages", {}).get("completion_rate", 0),
            "issue_rate": aggregate.get("averages", {}).get("issue_rate", 0)
        },
        "averages_per_session": aggregate.get("averages", {}),
        "by_project": aggregate["by_project"],
        "by_task_type": aggregate["by_task_type"],
        "tools_usage": dict(list(aggregate["tools_usage"].items())[:15]),
        "claude_code_features": {
            "skills_usage": cc_features.get("skills_usage", {}),
            "agents_usage": cc_features.get("agents_usage", {}),
            "slash_commands_usage": cc_features.get("slash_commands_usage", {}),
            "totals": cc_features.get("totals", {})
        },
        "detected_patterns": {
            "common_successes": aggregate["common_successes"],
            "common_issues": aggregate["common_issues"],
            "sessions_with_issues": aggregate["sessions_with_issues"],
            "sessions_likely_completed": aggregate.get("sessions_completed", 0)
        },
        "sessions": condensed_sessions
    }

    # Add global stats from ~/.claude.json if provided
    if global_stats:
        report_data["global_stats"] = {
            "source": global_stats.get("source", "~/.claude.json"),
            "usage_overview": global_stats.get("global_stats", {}),
            "skill_usage": global_stats.get("skill_usage", {}),
            "tips_history": global_stats.get("tips_history", {}),
        }

    return report_data


def save_report_data(report_data: Dict, output_dir: Path) -> Path:
    """Save the report data to JSON file."""
    # Create directory structure
    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename with report duration (start_date to end_date)
    start_date = report_data["report_metadata"]["start_date"]
    end_date = report_data["report_metadata"]["end_date"]
    project_filter = report_data["report_metadata"].get("project_filter")

    if project_filter:
        # Sanitize project name for filename (replace special chars)
        safe_project = "".join(c if c.isalnum() or c in "-_" else "_" for c in project_filter)
        filename = f"report_data_{start_date}_to_{end_date}_{safe_project}.json"
    else:
        filename = f"report_data_{start_date}_to_{end_date}.json"
    output_path = data_dir / filename

    with open(output_path, 'w') as f:
        json.dump(report_data, f, indent=2, default=str)

    return output_path


def print_summary(report_data: Dict):
    """Print a quick summary to console."""
    meta = report_data["report_metadata"]
    stats = report_data["aggregate_statistics"]
    features = report_data.get("claude_code_features", {})
    totals = features.get("totals", {})

    print("\n" + "=" * 50)
    print("REPORT DATA GENERATED")
    print("=" * 50)
    print(f"Period: {meta['period']} ({meta['start_date']} to {meta['end_date']})")
    if meta.get("project_filter"):
        print(f"Project Filter: {meta['project_filter']}")
    print(f"Sessions: {stats['total_sessions']}")
    print(f"Total Time: {stats['total_duration_hours']} hours")
    print(f"Completion Rate: {stats['completion_rate']}%")
    print(f"Issue Rate: {stats['issue_rate']}%")

    # Claude Code Features summary (from session data)
    if any(totals.get(k, 0) > 0 for k in totals):
        print("-" * 50)
        print("Claude Code Features (from sessions):")
        print(f"  Skills invoked: {totals.get('total_skills_invoked', 0)} (in {totals.get('sessions_using_skills', 0)} sessions)")
        print(f"  Agents spawned: {totals.get('total_agents_spawned', 0)} (in {totals.get('sessions_using_agents', 0)} sessions)")
        print(f"  Slash commands: {totals.get('total_slash_commands', 0)} (in {totals.get('sessions_using_slash_commands', 0)} sessions)")

    # Global stats from ~/.claude.json
    global_stats = report_data.get("global_stats", {})
    if global_stats:
        usage = global_stats.get("usage_overview", {})
        skill_usage = global_stats.get("skill_usage", {})
        print("-" * 50)
        print("Global Stats (from ~/.claude.json):")
        print(f"  Total startups: {usage.get('num_startups', 0)}")
        print(f"  Days since first use: {usage.get('days_since_first_use', 'N/A')}")
        print(f"  Prompt queue uses: {usage.get('prompt_queue_use_count', 0)}")
        print(f"  Total skill invocations (all time): {skill_usage.get('total_skill_invocations', 0)}")
        print(f"  Unique skills used (all time): {skill_usage.get('unique_skills_used', 0)}")

    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(
        description="Generate Claude Code usage report data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python generate_report.py --period weekly
    python generate_report.py --period monthly
    python generate_report.py --days 14
    python generate_report.py --start 2025-12-01 --end 2025-12-15
    python generate_report.py --project myapp
    python generate_report.py --period weekly --project ema
        """
    )

    # Period options (mutually exclusive in spirit but we handle precedence)
    parser.add_argument(
        "--period",
        choices=["daily", "weekly", "monthly"],
        default="weekly",
        help="Predefined time period (default: weekly)"
    )
    parser.add_argument(
        "--days",
        type=int,
        help="Number of days to look back (overrides --period)"
    )
    parser.add_argument(
        "--start",
        type=str,
        help="Start date in YYYY-MM-DD format (requires --end)"
    )
    parser.add_argument(
        "--end",
        type=str,
        help="End date in YYYY-MM-DD format (requires --start)"
    )

    # Output options
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./reports",
        help="Output directory for report data (default: ./reports)"
    )
    parser.add_argument(
        "--project",
        type=str,
        help="Filter by project name (partial match)"
    )
    parser.add_argument(
        "--compare-previous",
        action="store_true",
        help="Include comparison with previous period of same length"
    )
    parser.add_argument(
        "--session",
        type=str,
        help="Analyze a single session by its full UUID"
    )

    args = parser.parse_args()

    # Validate date arguments
    if (args.start and not args.end) or (args.end and not args.start):
        parser.error("--start and --end must be used together")

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
        deep_dive = generate_deep_dive_data(session_data, summary, analyzed)

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

    # Determine date range
    start_date, end_date = get_date_range(args)
    days_back = calculate_days_back(start_date)

    # Determine period name for report
    if args.start and args.end:
        period_name = "custom"
    elif args.days:
        period_name = f"{args.days}_days"
    else:
        period_name = args.period

    if args.project:
        print(f"Extracting sessions for project '{args.project}' from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}...")
    else:
        print(f"Extracting sessions from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}...")

    # Extract sessions
    extractor = SessionExtractor()
    sessions_info = extractor.get_all_sessions(
        days_back=days_back,
        project_filter=args.project
    )

    print(f"Found {len(sessions_info)} sessions")

    if not sessions_info:
        print("No sessions found for the specified period.")
        return

    # Parse and prepare sessions
    sessions = []
    skipped_empty = 0
    skipped_idle = 0

    # Idle session thresholds
    IDLE_DURATION_THRESHOLD_MINUTES = 360  # 6 hours
    IDLE_TOOL_CALLS_THRESHOLD = 5

    for i, session_info in enumerate(sessions_info):
        print(f"Processing {i+1}/{len(sessions_info)}: {session_info['session_id'][:8]}...")
        session_data = extractor.parse_session(session_info)
        summary = generate_summary_for_analysis(session_data)

        # Filter out empty sessions (no duration and no tool calls)
        duration = summary.get("metadata", {}).get("duration_minutes", 0) or 0
        tool_calls = summary.get("statistics", {}).get("tool_call_count", 0)

        if duration <= 0 and tool_calls == 0:
            skipped_empty += 1
            continue

        # Filter out idle sessions (>6hr with <5 tool calls)
        # These are likely abandoned sessions that skew duration averages
        if duration > IDLE_DURATION_THRESHOLD_MINUTES and tool_calls < IDLE_TOOL_CALLS_THRESHOLD:
            skipped_idle += 1
            continue

        sessions.append(summary)

    if skipped_empty > 0:
        print(f"Skipped {skipped_empty} empty sessions (duration <= 0 and tool_calls = 0)")
    if skipped_idle > 0:
        print(f"Skipped {skipped_idle} idle sessions (>6hr with <5 tool calls)")

    # Prepare filtered counts for metadata
    filtered_counts = {
        "empty_sessions_filtered": skipped_empty,
        "idle_sessions_filtered": skipped_idle
    }

    # Extract global stats from ~/.claude.json
    print("Extracting global stats from ~/.claude.json...")
    global_extractor = GlobalStatsExtractor()
    global_stats = global_extractor.get_all_stats(project_filter=args.project)

    # Generate report data
    report_data = generate_report_data(
        sessions, start_date, end_date, period_name,
        args.project, global_stats, filtered_counts
    )

    # Handle --compare-previous: extract and analyze previous period
    if args.compare_previous:
        period_days = (end_date - start_date).days
        previous_end = start_date
        previous_start = previous_end - timedelta(days=period_days)

        print(f"\nExtracting comparison data from {previous_start.strftime('%Y-%m-%d')} to {previous_end.strftime('%Y-%m-%d')}...")

        # Calculate days back for previous period
        prev_days_back = calculate_days_back(previous_start)

        # Extract previous period sessions
        prev_sessions_info = extractor.get_all_sessions(
            days_back=prev_days_back,
            project_filter=args.project
        )

        # Filter to only sessions within the previous period
        prev_sessions = []
        for session_info in prev_sessions_info:
            # Parse and check date
            session_data = extractor.parse_session(session_info)
            summary = generate_summary_for_analysis(session_data)

            # Get session timestamp
            session_date_str = summary.get("metadata", {}).get("start_time", "")
            if not session_date_str:
                continue

            try:
                session_dt = datetime.fromisoformat(session_date_str.replace("Z", "+00:00"))
                session_date = session_dt.replace(tzinfo=None)
            except:
                continue

            # Check if in previous period
            if not (previous_start <= session_date < previous_end):
                continue

            # Apply same filters as current period
            duration = summary.get("metadata", {}).get("duration_minutes", 0) or 0
            tool_calls = summary.get("statistics", {}).get("tool_call_count", 0)

            if duration <= 0 and tool_calls == 0:
                continue
            if duration > IDLE_DURATION_THRESHOLD_MINUTES and tool_calls < IDLE_TOOL_CALLS_THRESHOLD:
                continue

            prev_sessions.append(summary)

        print(f"Found {len(prev_sessions)} sessions in previous period")

        if prev_sessions:
            # Analyze previous sessions
            prev_analyzed = []
            for session in prev_sessions:
                analyzed = analyze_session_for_report(session)
                prev_analyzed.append({**session, **analyzed})

            # Generate aggregate for previous period
            prev_aggregate = generate_aggregate_report(prev_analyzed)

            # Calculate comparison
            # Need to run aggregate on current sessions to get activity_metrics
            current_analyzed = []
            for session in sessions:
                analyzed = analyze_session_for_report(session)
                current_analyzed.append({**session, **analyzed})
            current_full_aggregate = generate_aggregate_report(current_analyzed)

            comparison = calculate_comparison(current_full_aggregate, prev_aggregate)
            comparison["previous_period"] = {
                "start_date": previous_start.strftime("%Y-%m-%d"),
                "end_date": previous_end.strftime("%Y-%m-%d"),
                "total_sessions": len(prev_sessions)
            }

            report_data["comparison"] = comparison
            print(f"Comparison data added: {comparison['sessions']['delta']:+d} sessions ({comparison['sessions']['delta_pct']:+.1f}%)")
        else:
            report_data["comparison"] = {
                "has_comparison": False,
                "reason": "No sessions found in previous period"
            }

    # Save to file
    output_dir = Path(args.output_dir)
    output_path = save_report_data(report_data, output_dir)

    print_summary(report_data)
    print(f"\nReport data saved to: {output_path}")
    print(f"\nNext step: Claude Code will read this file and generate the final report.")


if __name__ == "__main__":
    main()
