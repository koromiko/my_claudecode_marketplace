#!/usr/bin/env python3
"""
Claude Code Session Analyzer

This script analyzes extracted sessions and generates quality assessment summaries
suitable for creating a comprehensive usage report.
"""

import json
import re
import statistics
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Any, Optional, Tuple
import argparse
import glob as glob_module


def detect_input_format(data: Any) -> str:
    """Detect the format of the input data."""
    if isinstance(data, dict):
        # report_data format has these top-level keys
        if "report_metadata" in data and "sessions" in data:
            return "report_data"
        # Could be a single session in extract format
        if "metadata" in data and "statistics" in data:
            return "extract_sessions"
    elif isinstance(data, list):
        if len(data) > 0:
            first = data[0]
            # extract_sessions format has metadata and statistics
            if "metadata" in first and "statistics" in first:
                return "extract_sessions"
            # report_data sessions have stats (not statistics)
            if "stats" in first and "outcome" in first:
                return "report_data_sessions"
    return "unknown"


def normalize_session(session: Dict, input_format: str) -> Dict:
    """Normalize session data to a common format for analysis."""
    if input_format in ["extract_sessions"]:
        # Already in expected format
        return session

    elif input_format in ["report_data", "report_data_sessions"]:
        # Convert from report_data format to extract_sessions format
        stats = session.get("stats", {})
        return {
            "session_id": session.get("session_id", "unknown"),
            "project": session.get("project", "unknown"),
            "metadata": {
                "duration_minutes": session.get("duration_minutes", 0),
                "date": session.get("date", "unknown"),
                "git_branch": session.get("git_branch"),
                "outcome": session.get("outcome"),  # Actual outcome from report
                "full_project_path": session.get("full_project_path")
            },
            "statistics": {
                "user_messages": stats.get("user_messages", 0),
                "assistant_messages": stats.get("assistant_messages", 0),
                "tool_call_count": stats.get("tool_calls", 0),
                "tools_used": stats.get("tools_used", []),
                "total_turns": stats.get("user_messages", 0) + stats.get("assistant_messages", 0)
            },
            "claude_code_features": session.get("claude_code_features", {}),
            "task_context": {
                "initial_prompts": [session.get("task_summary", "")] if session.get("task_summary") else [],
                "commands_sample": [],  # Not available in report_data format
                "files_touched": ["file"] * stats.get("files_touched", 0)  # Placeholder for count
            },
            # Preserve original data
            "_original": {
                "task_type": session.get("task_type"),
                "key_topics": session.get("key_topics", []),
                "successes": session.get("successes", []),
                "issues": session.get("issues", [])
            }
        }

    return session


def load_sessions(input_path: str) -> Tuple[List[Dict], str]:
    """Load sessions from various input formats."""
    with open(input_path, 'r') as f:
        data = json.load(f)

    input_format = detect_input_format(data)

    if input_format == "report_data":
        # Extract sessions from report_data format
        sessions = data.get("sessions", [])
        normalized = [normalize_session(s, "report_data_sessions") for s in sessions]
        return normalized, input_format

    elif input_format == "report_data_sessions":
        # Already a list of report_data format sessions
        normalized = [normalize_session(s, input_format) for s in data]
        return normalized, input_format

    elif input_format == "extract_sessions":
        # Already in expected format
        return data, input_format

    else:
        # Try to treat as list of sessions
        if isinstance(data, list):
            return data, "unknown"
        raise ValueError(f"Unknown input format for file: {input_path}")


def find_latest_report_data(base_dir: str = ".") -> Optional[str]:
    """Find the most recent report_data file."""
    patterns = [
        f"{base_dir}/reports/data/report_data_*.json",
        f"{base_dir}/report_data_*.json",
        f"{base_dir}/*.json"
    ]

    all_files = []
    for pattern in patterns:
        all_files.extend(glob_module.glob(pattern))

    # Filter for report_data files and sort by name (date in filename)
    report_files = [f for f in all_files if "report_data" in f]
    if report_files:
        return sorted(report_files)[-1]  # Latest by filename

    return None


def extract_jira_ticket(git_branch: Optional[str]) -> Optional[str]:
    """Extract JIRA ticket from git branch name."""
    if not git_branch:
        return None
    # Match patterns like jira/JSO-3450, jira/EMOBAPP-3336, etc.
    match = re.search(r'([A-Z]+-\d+)', git_branch, re.IGNORECASE)
    return match.group(1).upper() if match else None


def classify_git_operations(commands: List[str]) -> Dict[str, Any]:
    """Classify git operations into categories for better completion detection.

    Args:
        commands: List of command strings from the session

    Returns:
        Dict with flags:
        - has_commit: True if a git commit was made
        - has_push: True if git push was executed
        - has_add: True if git add was executed
        - read_only: True if only read-only git operations (status/log/diff/branch/show)
        - has_failed_commit: True if commit appears to have failed (error in output)
        - commit_count: Number of commit commands
        - git_commands: List of all git commands found
    """
    git_commands = []
    has_commit = False
    has_push = False
    has_add = False
    has_failed_commit = False
    commit_count = 0

    for cmd in commands:
        cmd_lower = cmd.lower()
        if 'git' not in cmd_lower:
            continue

        git_commands.append(cmd)

        # Check for commit
        if re.search(r'\bgit\s+commit\b', cmd_lower):
            has_commit = True
            commit_count += 1
            # Check if commit failed
            if 'error' in cmd_lower or 'fail' in cmd_lower or 'abort' in cmd_lower:
                has_failed_commit = True

        # Check for push
        if re.search(r'\bgit\s+push\b', cmd_lower):
            has_push = True

        # Check for add
        if re.search(r'\bgit\s+add\b', cmd_lower):
            has_add = True

    # Determine if only read-only operations
    read_only_patterns = [
        r'\bgit\s+status\b',
        r'\bgit\s+log\b',
        r'\bgit\s+diff\b',
        r'\bgit\s+branch\b',
        r'\bgit\s+show\b',
        r'\bgit\s+remote\b',
        r'\bgit\s+fetch\b',
        r'\bgit\s+ls-files\b',
        r'\bgit\s+rev-parse\b',
    ]
    read_only = True
    for cmd in git_commands:
        cmd_lower = cmd.lower()
        is_read_only = any(re.search(pat, cmd_lower) for pat in read_only_patterns)
        if not is_read_only:
            read_only = False
            break

    # If no git commands at all, read_only is False (nothing to read)
    if not git_commands:
        read_only = False

    return {
        "has_commit": has_commit,
        "has_push": has_push,
        "has_add": has_add,
        "read_only": read_only,
        "has_failed_commit": has_failed_commit,
        "commit_count": commit_count,
        "git_commands": git_commands
    }


def is_valid_session(session: Dict) -> bool:
    """Check if a session has valid data for analysis."""
    duration = session.get("metadata", {}).get("duration_minutes", 0)
    user_msgs = session.get("statistics", {}).get("user_messages", 0)

    # Filter out sessions with no activity or invalid duration
    if duration is None or duration < 0:
        return False
    if user_msgs <= 0:
        return False
    return True


def calculate_percentile(values: List[float], percentile: int) -> float:
    """Calculate the nth percentile of a list of values."""
    if not values:
        return 0
    sorted_values = sorted(values)
    index = (percentile / 100) * (len(sorted_values) - 1)
    lower = int(index)
    upper = lower + 1
    if upper >= len(sorted_values):
        return sorted_values[-1]
    weight = index - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def classify_session_type(
    duration_minutes: float,
    tool_calls: int,
    has_edits: bool,
    tools_used: List[str]
) -> str:
    """Classify session as 'work' or 'lookup' based on activity patterns.

    Lookup sessions are characterized by:
    - Short duration (<5 min)
    - Few tool calls (<10)
    - No file edits
    - Primarily read operations (Read, Grep, Glob)

    Work sessions are characterized by:
    - Longer duration (>=5 min) OR
    - Many tool calls (>=10) OR
    - Has file edits

    Args:
        duration_minutes: Session duration in minutes
        tool_calls: Total number of tool calls
        has_edits: Whether Edit/Write tools were used
        tools_used: List of tool names used

    Returns:
        "lookup" or "work"
    """
    # Work session indicators
    if has_edits:
        return "work"
    if duration_minutes >= 5:
        return "work"
    if tool_calls >= 10:
        return "work"

    # Check if primarily read operations
    read_tools = {"Read", "Grep", "Glob", "Bash"}
    write_tools = {"Edit", "Write", "NotebookEdit"}

    tools_set = set(tools_used)
    has_write_tools = bool(tools_set & write_tools)

    if has_write_tools:
        return "work"

    # If short, few tool calls, and no edits -> lookup
    return "lookup"


def calculate_duration_histogram(durations: List[float]) -> Dict[str, int]:
    """Calculate duration distribution in predefined buckets.

    Buckets:
    - <1min: Very quick lookups
    - 1-5min: Quick tasks
    - 5-15min: Short tasks
    - 15-30min: Medium tasks
    - 30-60min: Long tasks
    - 60min+: Very long tasks

    Args:
        durations: List of session durations in minutes

    Returns:
        Dict mapping bucket labels to counts
    """
    buckets = {
        "<1min": 0,
        "1-5min": 0,
        "5-15min": 0,
        "15-30min": 0,
        "30-60min": 0,
        "60min+": 0
    }

    for d in durations:
        if d < 1:
            buckets["<1min"] += 1
        elif d < 5:
            buckets["1-5min"] += 1
        elif d < 15:
            buckets["5-15min"] += 1
        elif d < 30:
            buckets["15-30min"] += 1
        elif d < 60:
            buckets["30-60min"] += 1
        else:
            buckets["60min+"] += 1

    return buckets


def classify_task_type(
    prompts: List[str],
    commands: List[str],
    tools: List[str],
    duration: Optional[float] = None,
    tool_calls: Optional[int] = None,
    has_edits: Optional[bool] = None
) -> str:
    """Classify the type of task based on context clues and session characteristics.

    Classification priority (more specific patterns first):
    1. bug_fix - fixing broken things
    2. testing - writing/running tests
    3. config - infrastructure/setup work
    4. review - code review tasks
    5. debug - investigation without necessarily fixing
    6. refactor - code cleanup/optimization
    7. feature - adding new functionality
    8. update - modifying existing functionality
    9. lookup - quick information retrieval
    10. exploration - learning/documentation
    11. general - fallback (or "lookup" if session characteristics indicate it)
    """
    all_text = " ".join(str(p) for p in prompts).lower()
    all_commands = " ".join(commands).lower()

    # Detect likely lookup sessions from session characteristics
    # Short, read-only sessions with few tool calls default to "lookup" instead of "general"
    is_likely_lookup = (
        duration is not None
        and duration < 5
        and not has_edits
        and (tool_calls or 0) < 10
    )

    # Bug fix - highest priority for error-related tasks
    if any(word in all_text for word in [
        "bug", "fix", "error", "issue", "broken", "doesn't work", "not working",
        "failing", "crash", "exception", "resolve", "patch"
    ]):
        return "bug_fix"

    # Testing - test-related work
    if any(word in all_text for word in [
        "test", "spec", "e2e", "unit test", "integration test", "coverage",
        "assertion", "mock", "stub", "jest", "pytest", "testing"
    ]):
        return "testing"

    # Config/Infrastructure - setup and configuration
    if any(word in all_text for word in [
        "config", "setup", "install", "terraform", "infra", "infrastructure",
        "deploy", "ci", "cd", "pipeline", "docker", "kubernetes", "k8s",
        "environment", "env", "yaml", "json config"
    ]):
        return "config"

    # Code review - reviewing changes
    if any(word in all_text for word in [
        "review", "pr", "pull request", "code review", "feedback",
        "approve", "merge", "diff", "changes"
    ]):
        return "review"

    # Exploration - learning and documentation (check before debug to catch "understand" in learning context)
    if any(phrase in all_text for phrase in [
        "explain", "what is", "how does", "document", "learn",
        "describe", "tell me about", "help me understand"
    ]):
        return "exploration"

    # Debug/Investigation - understanding without necessarily changing
    if any(word in all_text for word in [
        "debug", "investigate", "why", "understand", "trace", "log",
        "what's happening", "look into", "figure out", "diagnose"
    ]):
        return "debug"

    # Refactor - code improvement
    if any(word in all_text for word in [
        "refactor", "clean", "improve", "optimize", "restructure",
        "reorganize", "simplify", "rename", "extract", "consolidate"
    ]):
        return "refactor"

    # Feature - creating something new (check after more specific types)
    if any(word in all_text for word in [
        "add", "create", "implement", "new feature", "build", "introduce",
        "develop", "make", "generate", "design"
    ]):
        return "feature"

    # Update - modifying existing functionality
    if any(word in all_text for word in [
        "update", "change", "modify", "edit", "adjust", "tweak",
        "alter", "revise", "enhance", "upgrade", "migrate"
    ]):
        return "update"

    # Lookup - quick information retrieval (short queries)
    if any(word in all_text for word in [
        "find", "search", "locate", "where", "show me", "list",
        "get", "fetch", "check", "verify", "validate", "confirm"
    ]):
        return "lookup"

    # If session characteristics indicate a lookup, use that instead of "general"
    if is_likely_lookup:
        return "lookup"

    return "general"


def evaluate_task_completion(
    task_type: str,
    has_edits: bool,
    has_reads: bool,
    files_touched: int,
    git_ops: Dict[str, Any],
    commands: List[str],
    tools_used: List[str],
    duration: float,
    user_msgs: int,
    failure_signals: List[Dict]
) -> Dict[str, Any]:
    """Evaluate completion based on task type-specific criteria.

    Args:
        task_type: The classified task type
        has_edits: Whether Edit/Write tools were used
        has_reads: Whether Read/Grep/Glob tools were used
        files_touched: Number of files touched
        git_ops: Result from classify_git_operations()
        commands: List of command strings
        tools_used: List of tool names used
        duration: Session duration in minutes
        user_msgs: Number of user messages
        failure_signals: Result from detect_failure_signals()

    Returns:
        Dict with:
        - completed: bool indicating likely completion
        - completion_type: specific completion category
        - criteria_met: list of criteria that were satisfied
        - criteria_missing: list of expected criteria not met
    """
    criteria_met = []
    criteria_missing = []

    # Check for test execution in commands
    test_patterns = [r'\btest\b', r'\bpytest\b', r'\bjest\b', r'\bnpm\s+test\b', r'\byarn\s+test\b', r'\bgradle.*test\b']
    has_test_run = any(
        any(re.search(pat, cmd.lower()) for pat in test_patterns)
        for cmd in commands
    )

    # Check for build commands
    build_patterns = [r'\bbuild\b', r'\bcompile\b', r'\bnpm\s+run\b', r'\byarn\b', r'\bgradle\b', r'\bmake\b']
    has_build = any(
        any(re.search(pat, cmd.lower()) for pat in build_patterns)
        for cmd in commands
    )

    # Calculate failure severity
    total_failure_severity = sum(s.get("severity", 0) for s in failure_signals)
    has_high_severity_failure = any(s.get("severity", 0) >= 2 for s in failure_signals)

    # Task-type specific evaluation
    if task_type == "bug_fix":
        # Bug fixes should have edits AND (test run OR git commit)
        if has_edits:
            criteria_met.append("has_edits")
        else:
            criteria_missing.append("has_edits")

        if has_test_run or git_ops["has_commit"]:
            criteria_met.append("has_verification")
        else:
            criteria_missing.append("has_verification (test or commit)")

        completed = has_edits and (has_test_run or git_ops["has_commit"])

    elif task_type == "feature":
        # Features should have code written
        if has_edits:
            criteria_met.append("has_edits")
        else:
            criteria_missing.append("has_edits")

        if files_touched > 0:
            criteria_met.append("files_touched")
        else:
            criteria_missing.append("files_touched")

        completed = has_edits and files_touched > 0

    elif task_type == "refactor":
        # Refactoring should touch multiple files
        if has_edits:
            criteria_met.append("has_edits")
        else:
            criteria_missing.append("has_edits")

        if files_touched > 1:
            criteria_met.append("multiple_files_touched")
        else:
            criteria_missing.append("multiple_files_touched (>1)")

        completed = has_edits and files_touched > 1

    elif task_type == "debug":
        # Debug/investigation may not need edits, just investigation time
        if has_reads:
            criteria_met.append("has_reads")

        if duration > 5:
            criteria_met.append("sufficient_investigation_time")
        else:
            criteria_missing.append("sufficient_investigation_time (>5 min)")

        # Debug is complete if there was meaningful investigation
        completed = has_reads and duration > 5 and user_msgs > 1

    elif task_type == "testing":
        # Testing should run tests
        if has_test_run:
            criteria_met.append("test_execution")
        else:
            criteria_missing.append("test_execution")

        # Also count test file creation
        if has_edits:
            criteria_met.append("has_edits")

        completed = has_test_run

    elif task_type == "config":
        # Config can be either bash commands or file edits
        if has_edits:
            criteria_met.append("has_edits")

        if "Bash" in tools_used:
            criteria_met.append("bash_execution")

        completed = has_edits or "Bash" in tools_used

    elif task_type == "exploration":
        # Exploration just needs reads and user interaction
        if has_reads:
            criteria_met.append("has_reads")
        else:
            criteria_missing.append("has_reads")

        if user_msgs > 1:
            criteria_met.append("user_interaction")
        else:
            criteria_missing.append("user_interaction (>1 message)")

        completed = has_reads and user_msgs > 1

    else:  # "general" - fallback to original heuristic
        if has_edits:
            criteria_met.append("has_edits")

        if files_touched > 0:
            criteria_met.append("files_touched")

        if git_ops["has_commit"] or git_ops["has_push"]:
            criteria_met.append("git_changes")

        # Original heuristic
        completed = has_edits or (files_touched > 0 and (git_ops["has_commit"] or git_ops["has_push"]))

    # Downgrade completion if there are significant failure signals
    if completed and has_high_severity_failure:
        completed = False
        criteria_missing.append("failure_signals_detected")

    # Determine completion type
    if completed:
        completion_type = "completed"
    elif len(criteria_met) > 0 and len(criteria_met) > len(criteria_missing):
        completion_type = "partially_completed"
    else:
        completion_type = "not_completed"

    return {
        "completed": completed,
        "completion_type": completion_type,
        "criteria_met": criteria_met,
        "criteria_missing": criteria_missing,
        "failure_severity": total_failure_severity
    }


def calculate_completion_confidence(
    task_type: str,
    has_edits: bool,
    has_reads: bool,
    files_touched: int,
    git_ops: Dict[str, Any],
    has_test_run: bool,
    failure_signals: List[Dict],
    duration: float,
    user_msgs: int,
    completion_eval: Dict[str, Any]
) -> Dict[str, Any]:
    """Calculate confidence score (0-100) for completion determination.

    Args:
        task_type: The classified task type
        has_edits: Whether Edit/Write tools were used
        has_reads: Whether Read/Grep/Glob tools were used
        files_touched: Number of files touched
        git_ops: Result from classify_git_operations()
        has_test_run: Whether tests were executed
        failure_signals: Result from detect_failure_signals()
        duration: Session duration in minutes
        user_msgs: Number of user messages
        completion_eval: Result from evaluate_task_completion()

    Returns:
        Dict with:
        - score: 0-100 confidence score
        - positive_signals: list of signals that increased confidence
        - negative_signals: list of signals that decreased confidence
        - assessment: "high" (>=70), "medium" (40-69), or "low" (<40)
    """
    score = 50  # Base score
    positive_signals = []
    negative_signals = []

    # ===== Positive signals =====

    # Code changes made (+15)
    if has_edits:
        score += 15
        positive_signals.append(("has_edits", 15))

    # Successful git commit (+20) - strong completion signal
    if git_ops["has_commit"] and not git_ops["has_failed_commit"]:
        score += 20
        positive_signals.append(("successful_commit", 20))

    # Git push (+10) - even stronger signal
    if git_ops["has_push"]:
        score += 10
        positive_signals.append(("git_push", 10))

    # Tests ran (+15)
    if has_test_run:
        score += 15
        positive_signals.append(("tests_ran", 15))

    # Files touched (+10 for any, +5 more for >3 files)
    if files_touched > 0:
        score += 10
        positive_signals.append(("files_touched", 10))
        if files_touched > 3:
            score += 5
            positive_signals.append(("multiple_files", 5))

    # Reasonable duration for task type (+5)
    if task_type == "exploration" and duration > 3:
        score += 5
        positive_signals.append(("exploration_time", 5))
    elif task_type in ["bug_fix", "feature", "refactor"] and duration > 10:
        score += 5
        positive_signals.append(("sufficient_work_time", 5))

    # User engaged (>2 messages) (+5)
    if user_msgs > 2:
        score += 5
        positive_signals.append(("user_engagement", 5))

    # ===== Negative signals =====

    # Error patterns in commands
    error_signals = [s for s in failure_signals if s.get("type") == "error_in_commands"]
    if error_signals:
        penalty = min(20, sum(s.get("severity", 1) * 5 for s in error_signals))
        score -= penalty
        negative_signals.append(("errors_detected", -penalty))

    # Failed git commit (-15)
    if git_ops["has_failed_commit"]:
        score -= 15
        negative_signals.append(("failed_commit", -15))

    # High retry ratio (-15)
    retry_signals = [s for s in failure_signals if s.get("type") == "high_retry_ratio"]
    if retry_signals:
        score -= 15
        negative_signals.append(("high_retry_ratio", -15))

    # User frustration indicators (-20)
    frustration_signals = [s for s in failure_signals if s.get("type") == "user_frustration"]
    if frustration_signals:
        score -= 20
        negative_signals.append(("user_frustration", -20))

    # Quick abandonment (-20)
    abandon_signals = [s for s in failure_signals if s.get("type") == "quick_abandonment"]
    if abandon_signals:
        score -= 20
        negative_signals.append(("quick_abandonment", -20))

    # No tangible output after significant time (-10)
    no_output_signals = [s for s in failure_signals if s.get("type") == "no_tangible_output"]
    if no_output_signals:
        score -= 10
        negative_signals.append(("no_tangible_output", -10))

    # Task-type specific adjustments
    if task_type == "exploration" and has_reads and not has_edits:
        # Exploration without edits is fine
        score += 10
        positive_signals.append(("exploration_reads_ok", 10))
    elif task_type == "debug" and has_reads and duration > 5:
        # Debug investigation is valid
        score += 10
        positive_signals.append(("debug_investigation", 10))

    # Use completion evaluation criteria
    criteria_met_count = len(completion_eval.get("criteria_met", []))
    criteria_missing_count = len(completion_eval.get("criteria_missing", []))

    if criteria_met_count > criteria_missing_count:
        score += 10
        positive_signals.append(("criteria_met", 10))
    elif criteria_missing_count > criteria_met_count:
        score -= 10
        negative_signals.append(("criteria_missing", -10))

    # Clamp score to 0-100
    score = max(0, min(100, score))

    # Determine assessment level
    if score >= 70:
        assessment = "high"
    elif score >= 40:
        assessment = "medium"
    else:
        assessment = "low"

    return {
        "score": score,
        "positive_signals": positive_signals,
        "negative_signals": negative_signals,
        "assessment": assessment
    }


# Default confidence threshold for considering a session "likely completed"
COMPLETION_CONFIDENCE_THRESHOLD = 60


def detect_issues(session: Dict) -> List[Dict]:
    """Detect potential issues in a session."""
    issues = []

    # Check for error indicators in commands
    commands = session.get("task_context", {}).get("commands_sample", [])
    for cmd in commands:
        if "error" in cmd.lower() or "fail" in cmd.lower():
            issues.append({
                "type": "command_error",
                "description": f"Potential error in command execution",
                "evidence": cmd[:100]
            })

    # Check for high tool call count (might indicate struggles)
    tool_count = session.get("statistics", {}).get("tool_call_count", 0)
    user_msgs = session.get("statistics", {}).get("user_messages", 0)

    if user_msgs > 0 and tool_count / user_msgs > 10:
        issues.append({
            "type": "high_tool_usage",
            "description": "High tool calls per user message ratio - may indicate difficulty completing task",
            "evidence": f"{tool_count} tool calls for {user_msgs} user messages"
        })

    # Check for very short sessions with many messages (potential confusion)
    duration = session.get("metadata", {}).get("duration_minutes", 0)
    total_turns = session.get("statistics", {}).get("total_turns", 0)

    if duration < 5 and total_turns > 20:
        issues.append({
            "type": "rapid_interactions",
            "description": "Many interactions in short time - potential rapid-fire corrections",
            "evidence": f"{total_turns} turns in {duration} minutes"
        })

    return issues


def detect_failure_signals(session: Dict) -> List[Dict]:
    """Detect signals that indicate a session failed or was abandoned.

    Returns a list of failure signal dicts with type, severity (1-3), and evidence.
    Higher severity indicates stronger failure signal.
    """
    signals = []

    commands = session.get("task_context", {}).get("commands_sample", [])
    prompts = session.get("task_context", {}).get("initial_prompts", [])
    tools_used = session.get("statistics", {}).get("tools_used", [])
    tool_count = session.get("statistics", {}).get("tool_call_count", 0)
    user_msgs = session.get("statistics", {}).get("user_messages", 0)
    duration = session.get("metadata", {}).get("duration_minutes", 0) or 0

    # 1. Error patterns in bash output/commands
    error_patterns = [
        r'\berror\b', r'\bfailed\b', r'\bfailure\b', r'\bexception\b',
        r'\bcrash\b', r'\btimeout\b', r'\bdenied\b', r'\bforbidden\b',
        r'\bnot found\b', r'\bcannot\b', r'\bunable to\b'
    ]
    error_commands = []
    for cmd in commands:
        cmd_lower = cmd.lower()
        for pattern in error_patterns:
            if re.search(pattern, cmd_lower):
                error_commands.append(cmd[:100])
                break

    if error_commands:
        severity = min(3, len(error_commands))  # More errors = higher severity
        signals.append({
            "type": "error_in_commands",
            "severity": severity,
            "description": f"Error patterns found in {len(error_commands)} command(s)",
            "evidence": error_commands[:3]
        })

    # 2. High retry ratio - same tool called repeatedly
    # This is a heuristic: high tool calls with low user messages might indicate retries
    if user_msgs > 0 and tool_count > 0:
        ratio = tool_count / user_msgs
        if ratio > 15:  # Very high ratio suggests struggling/retrying
            signals.append({
                "type": "high_retry_ratio",
                "severity": 2,
                "description": f"High tool-to-message ratio ({ratio:.1f}:1) suggests repeated attempts",
                "evidence": f"{tool_count} tool calls for {user_msgs} user messages"
            })

    # 3. Abandoned session signals
    # 3a. Very short session with many tool calls (started but gave up quickly)
    if duration < 2 and tool_count > 5:
        signals.append({
            "type": "quick_abandonment",
            "severity": 2,
            "description": "Very short session with significant activity - possible early abandonment",
            "evidence": f"{tool_count} tool calls in {duration:.1f} minutes"
        })

    # 3b. Many reads but no edits (investigation that didn't lead to action)
    has_reads = any(t in tools_used for t in ["Read", "Grep", "Glob"])
    has_edits = any(t in tools_used for t in ["Edit", "Write"])
    if has_reads and not has_edits and tool_count > 10:
        signals.append({
            "type": "read_without_edit",
            "severity": 1,
            "description": "Multiple read operations without any edits - investigation may have stalled",
            "evidence": f"Tools used: {tools_used}"
        })

    # 3c. Git operations that indicate failed workflow
    git_ops = classify_git_operations(commands)
    if git_ops["has_failed_commit"]:
        signals.append({
            "type": "failed_git_commit",
            "severity": 2,
            "description": "Git commit appears to have failed",
            "evidence": git_ops["git_commands"][:3]
        })

    # 4. User frustration indicators in prompts
    frustration_patterns = [
        r'\bnever\s*mind\b', r'\bforget\s*it\b', r'\bgive\s*up\b',
        r'\bdoesn\'?t\s*work\b', r'\bnot\s*working\b', r'\bstop\b',
        r'\bcancel\b', r'\babort\b', r'\bwrong\b', r'\bbroken\b',
        r'\bundo\b', r'\brevert\b', r'\btry\s*again\b', r'\bstill\s*broken\b'
    ]
    frustration_found = []
    for prompt in prompts:
        if isinstance(prompt, str):
            prompt_lower = prompt.lower()
            for pattern in frustration_patterns:
                if re.search(pattern, prompt_lower):
                    frustration_found.append(prompt[:50])
                    break

    if frustration_found:
        signals.append({
            "type": "user_frustration",
            "severity": 2,
            "description": "User prompts contain frustration indicators",
            "evidence": frustration_found[:3]
        })

    # 5. Session ends without clear resolution
    # Check if there's a git commit/push or file changes at the end
    if duration > 5 and not has_edits and not git_ops["has_commit"]:
        if tool_count > 10:
            signals.append({
                "type": "no_tangible_output",
                "severity": 1,
                "description": "Significant session activity but no file changes or commits",
                "evidence": f"Duration: {duration:.1f}m, Tools: {tool_count}, No edits/commits"
            })

    return signals


def detect_successes(session: Dict) -> List[Dict]:
    """Detect indicators of successful outcomes."""
    successes = []

    tools_used = session.get("statistics", {}).get("tools_used", [])

    # Successful file edits
    if "Edit" in tools_used or "Write" in tools_used:
        files_touched = session.get("task_context", {}).get("files_touched", [])
        if files_touched:
            successes.append({
                "type": "code_changes",
                "description": f"Successfully modified {len(files_touched)} file(s)",
                "evidence": files_touched[:5]
            })

    # Successful command execution
    commands = session.get("task_context", {}).get("commands_sample", [])
    build_commands = [c for c in commands if any(x in c.lower() for x in ["build", "test", "npm", "yarn", "gradle"])]
    if build_commands:
        successes.append({
            "type": "build_commands",
            "description": "Executed build/test commands",
            "evidence": build_commands[:3]
        })

    # Git operations
    git_commands = [c for c in commands if "git" in c.lower()]
    if git_commands:
        successes.append({
            "type": "git_operations",
            "description": "Performed git operations",
            "evidence": git_commands[:3]
        })

    return successes


def extract_key_topics(prompts: List[Any]) -> List[str]:
    """Extract key topics/keywords from user prompts."""
    topics = set()

    # Common technical terms to look for
    tech_terms = [
        "api", "database", "auth", "login", "test", "build", "deploy",
        "component", "hook", "state", "redux", "react", "typescript",
        "error", "bug", "fix", "feature", "refactor", "performance",
        "terraform", "kubernetes", "docker", "ci", "cd", "pipeline"
    ]

    for prompt in prompts:
        if isinstance(prompt, str):
            text = prompt.lower()
            for term in tech_terms:
                if term in text:
                    topics.add(term)

    return list(topics)[:10]


def analyze_session(session: Dict) -> Dict:
    """Generate a comprehensive analysis for a single session."""

    prompts = session.get("task_context", {}).get("initial_prompts", [])
    commands = session.get("task_context", {}).get("commands_sample", [])
    tools_used = session.get("statistics", {}).get("tools_used", [])
    metadata = session.get("metadata", {})
    original = session.get("_original", {})  # Preserved data from report_data format

    # Extract first meaningful prompt as task description
    primary_task = ""
    for p in prompts:
        if isinstance(p, str) and len(p) > 20:
            # Clean up the prompt
            clean_prompt = p.replace("\n", " ").strip()
            primary_task = clean_prompt[:300]
            break

    # Calculate basic metrics (needed for task type classification)
    files_touched = len(session.get("task_context", {}).get("files_touched", []))
    has_edits = "Edit" in tools_used or "Write" in tools_used
    has_reads = any(t in tools_used for t in ["Read", "Grep", "Glob"])
    tool_calls = session.get("statistics", {}).get("tool_call_count", 0)
    user_msgs = session.get("statistics", {}).get("user_messages", 0)
    duration = metadata.get("duration_minutes", 0) or 0

    # Use original data if available, otherwise detect with session characteristics
    task_type = original.get("task_type") or classify_task_type(
        prompts, commands, tools_used,
        duration=duration, tool_calls=tool_calls, has_edits=has_edits
    )

    # Use original issues/successes if available, otherwise detect
    if original.get("issues"):
        issues = [{"type": "reported_issue", "description": i, "evidence": ""} for i in original["issues"]]
    else:
        issues = detect_issues(session)

    if original.get("successes"):
        successes = [{"type": "reported_success", "description": s, "evidence": ""} for s in original["successes"]]
    else:
        successes = detect_successes(session)

    # Use original topics if available, otherwise extract
    topics = original.get("key_topics") or extract_key_topics(prompts)

    # Classify git operations
    git_ops = classify_git_operations(commands)

    # Detect failure signals
    failure_signals = detect_failure_signals(session)

    # Check for test execution
    test_patterns = [r'\btest\b', r'\bpytest\b', r'\bjest\b', r'\bnpm\s+test\b', r'\byarn\s+test\b', r'\bgradle.*test\b']
    has_test_run = any(
        any(re.search(pat, cmd.lower()) for pat in test_patterns)
        for cmd in commands
    )

    # Evaluate task-type-specific completion criteria
    completion_eval = evaluate_task_completion(
        task_type=task_type,
        has_edits=has_edits,
        has_reads=has_reads,
        files_touched=files_touched,
        git_ops=git_ops,
        commands=commands,
        tools_used=tools_used,
        duration=duration,
        user_msgs=user_msgs,
        failure_signals=failure_signals
    )

    # Calculate completion confidence
    confidence = calculate_completion_confidence(
        task_type=task_type,
        has_edits=has_edits,
        has_reads=has_reads,
        files_touched=files_touched,
        git_ops=git_ops,
        has_test_run=has_test_run,
        failure_signals=failure_signals,
        duration=duration,
        user_msgs=user_msgs,
        completion_eval=completion_eval
    )

    # Determine outcome with expanded granularity
    actual_outcome = metadata.get("outcome", None)
    if actual_outcome:
        # Map legacy outcomes to new granular outcomes
        if actual_outcome == "completed":
            if issues:
                outcome = "completed_with_issues"
            else:
                outcome = "completed"
        elif actual_outcome == "had_issues":
            # Check if actually abandoned or just had issues
            has_abandon_signal = any(
                s.get("type") in ["quick_abandonment", "user_frustration"]
                for s in failure_signals
            )
            if has_abandon_signal:
                outcome = "abandoned"
            else:
                outcome = "completed_with_issues" if completion_eval["completed"] else "partially_completed"
        else:
            outcome = actual_outcome  # Keep as-is if it's already a new outcome type
    else:
        # Determine outcome from analysis
        # Classify session type for lookup detection
        session_type = classify_session_type(
            duration_minutes=duration,
            tool_calls=tool_calls,
            has_edits=has_edits,
            tools_used=tools_used
        )
        has_frustration = any(
            s.get("type") == "user_frustration" for s in failure_signals
        )

        if confidence["score"] >= COMPLETION_CONFIDENCE_THRESHOLD:
            if issues:
                outcome = "completed_with_issues"
            else:
                outcome = "completed"
        elif task_type == "exploration" and has_reads and user_msgs > 1:
            outcome = "exploration_complete"
        elif session_type == "lookup" and has_reads and user_msgs >= 1 and not has_frustration:
            # Short, read-only sessions that answered a question
            outcome = "lookup_complete"
        elif task_type == "lookup" and has_reads and user_msgs >= 1 and not has_frustration:
            # Keyword-classified lookup sessions that completed
            outcome = "lookup_complete"
        elif any(s.get("type") == "quick_abandonment" for s in failure_signals):
            outcome = "abandoned"
        elif has_frustration:
            outcome = "abandoned"
        elif completion_eval["completion_type"] == "partially_completed":
            outcome = "partially_completed"
        elif any(s.get("type") in ["error_in_commands", "failed_git_commit"] for s in failure_signals):
            # Check if it seems like external blocking
            if duration > 10 and tool_calls > 20:
                outcome = "blocked"
            else:
                outcome = "partially_completed"
        else:
            outcome = "unclear"

    # Determine likely_completed based on confidence threshold or lookup completion
    completed = (
        confidence["score"] >= COMPLETION_CONFIDENCE_THRESHOLD
        or outcome in ("lookup_complete", "exploration_complete")
    )

    # Extract JIRA ticket from branch
    git_branch = metadata.get("git_branch")
    jira_ticket = extract_jira_ticket(git_branch)

    efficiency = {
        "tools_per_file": round(tool_calls / files_touched, 2) if files_touched > 0 else 0,
        "tools_per_message": round(tool_calls / user_msgs, 2) if user_msgs > 0 else 0,
        "files_per_hour": round(files_touched / (duration / 60), 2) if duration > 0 else 0,
        "messages_per_minute": round(user_msgs / duration, 2) if duration > 0 else 0
    }

    # Claude Code feature usage
    features = session.get("claude_code_features", {})

    return {
        "session_id": session["session_id"],
        "project": session["project"],
        "metadata": session["metadata"],
        "statistics": session["statistics"],
        "claude_code_features": features,
        "task_analysis": {
            "primary_task": primary_task,
            "task_type": task_type,
            "key_topics": topics,
            "likely_completed": completed,
            "actual_outcome": outcome,
            "outcome": outcome,  # Add new outcome field for compatibility
            "jira_ticket": jira_ticket
        },
        "completion_analysis": {
            "confidence_score": confidence["score"],
            "confidence_assessment": confidence["assessment"],
            "positive_signals": confidence["positive_signals"],
            "negative_signals": confidence["negative_signals"],
            "completion_type": completion_eval["completion_type"],
            "criteria_met": completion_eval["criteria_met"],
            "criteria_missing": completion_eval["criteria_missing"],
            "failure_signals": failure_signals,
            "git_operations": git_ops
        },
        "quality_assessment": {
            "successes": successes,
            "issues": issues,
            "files_touched_count": files_touched,
            "tools_diversity": len(tools_used)
        },
        "efficiency_metrics": efficiency,
        "raw_context": {
            "sample_prompts": [str(p)[:200] for p in prompts[:3]],
            "sample_commands": commands[:5]
        }
    }


def generate_aggregate_report(analyzed_sessions: List[Dict]) -> Dict:
    """Generate aggregate statistics and insights across all sessions."""

    # Filter valid sessions
    valid_sessions = [s for s in analyzed_sessions if is_valid_session(s)]
    invalid_count = len(analyzed_sessions) - len(valid_sessions)

    report = {
        "summary": {
            "total_sessions": len(analyzed_sessions),
            "valid_sessions": len(valid_sessions),
            "invalid_sessions": invalid_count,
            "total_duration_minutes": 0,
            "total_user_messages": 0,
            "total_assistant_messages": 0,
            "total_tool_calls": 0,
            "total_files_touched": 0
        },
        "by_project": defaultdict(lambda: {
            "sessions": 0, "duration": 0, "tool_calls": 0,
            "completed": 0, "with_issues": 0, "files_touched": 0
        }),
        "by_task_type": defaultdict(int),
        "by_date": defaultdict(lambda: {"sessions": 0, "completed": 0, "duration": 0}),
        "by_outcome": defaultdict(int),
        "tools_usage": defaultdict(int),
        "topics_frequency": defaultdict(int),
        "jira_tickets": defaultdict(lambda: {"sessions": 0, "completed": 0}),
        "common_issues": defaultdict(int),
        "common_successes": defaultdict(int),
        "sessions_with_issues": 0,
        "sessions_completed": 0,
        # Activity tracking for more reliable metrics
        "sessions_with_edits": 0,
        "sessions_with_commits": 0,
        "sessions_with_tests": 0,
        # Session type tracking (work vs lookup)
        "by_session_type": {
            "work": {"count": 0, "total_duration": 0, "total_tool_calls": 0},
            "lookup": {"count": 0, "total_duration": 0, "total_tool_calls": 0}
        },
        # Claude Code feature tracking
        "claude_code_features": {
            "skills_usage": defaultdict(int),
            "agents_usage": defaultdict(int),
            "slash_commands_usage": defaultdict(int),
            "totals": {
                "total_skills_invoked": 0,
                "total_agents_spawned": 0,
                "total_slash_commands": 0,
                "sessions_using_skills": 0,
                "sessions_using_agents": 0,
                "sessions_using_slash_commands": 0
            }
        }
    }

    # Collect values for distribution analysis
    durations = []
    tool_calls_list = []
    files_touched_list = []
    confidence_scores = []  # Track completion confidence scores
    efficiency_metrics = {
        "tools_per_file": [],
        "tools_per_message": [],
        "files_per_hour": [],
        "messages_per_minute": []
    }

    for session in valid_sessions:
        stats = session.get("statistics", {})
        metadata = session.get("metadata", {})
        task_analysis = session.get("task_analysis", {})
        quality = session.get("quality_assessment", {})
        efficiency = session.get("efficiency_metrics", {})

        duration = metadata.get("duration_minutes", 0) or 0
        tool_count = stats.get("tool_call_count", 0)
        files_count = quality.get("files_touched_count", 0)

        # Summary totals
        report["summary"]["total_duration_minutes"] += duration
        report["summary"]["total_user_messages"] += stats.get("user_messages", 0)
        report["summary"]["total_assistant_messages"] += stats.get("assistant_messages", 0)
        report["summary"]["total_tool_calls"] += tool_count
        report["summary"]["total_files_touched"] += files_count

        # Collect for distributions
        if duration > 0:
            durations.append(duration)
        if tool_count > 0:
            tool_calls_list.append(tool_count)
        if files_count > 0:
            files_touched_list.append(files_count)

        # Efficiency metrics collection
        for key in efficiency_metrics:
            val = efficiency.get(key, 0)
            if val > 0:
                efficiency_metrics[key].append(val)

        # By project with cross-tabulation
        project = session.get("project", "unknown")
        project_short = project.split("/")[-1] if "/" in project else project
        report["by_project"][project_short]["sessions"] += 1
        report["by_project"][project_short]["duration"] += duration
        report["by_project"][project_short]["tool_calls"] += tool_count
        report["by_project"][project_short]["files_touched"] += files_count

        # Track completion and issues by project
        if task_analysis.get("likely_completed"):
            report["by_project"][project_short]["completed"] += 1
            report["sessions_completed"] += 1

        # Track activity metrics (more reliable than completion heuristics)
        tools_used = stats.get("tools_used", [])
        has_edits = "Edit" in tools_used or "Write" in tools_used
        if has_edits:
            report["sessions_with_edits"] += 1

        # Classify session type (work vs lookup)
        session_type = classify_session_type(
            duration_minutes=duration,
            tool_calls=tool_count,
            has_edits=has_edits,
            tools_used=tools_used
        )
        report["by_session_type"][session_type]["count"] += 1
        report["by_session_type"][session_type]["total_duration"] += duration
        report["by_session_type"][session_type]["total_tool_calls"] += tool_count

        # Check for git commits in completion analysis
        completion_analysis = session.get("completion_analysis", {})
        git_ops = completion_analysis.get("git_operations", {})
        if git_ops.get("has_commit") and not git_ops.get("has_failed_commit"):
            report["sessions_with_commits"] += 1

        # Check for test runs
        commands = session.get("task_context", {}).get("commands_sample", [])
        test_patterns = [r'\btest\b', r'\bpytest\b', r'\bjest\b', r'\bnpm\s+test\b', r'\byarn\s+test\b']
        has_tests = any(
            any(re.search(pat, cmd.lower()) for pat in test_patterns)
            for cmd in commands
        )
        if has_tests:
            report["sessions_with_tests"] += 1

        if quality.get("issues"):
            report["by_project"][project_short]["with_issues"] += 1
            report["sessions_with_issues"] += 1
            for issue in quality["issues"]:
                report["common_issues"][issue["type"]] += 1

        # By task type
        task_type = task_analysis.get("task_type", "unknown")
        report["by_task_type"][task_type] += 1

        # By date (time series)
        session_date = metadata.get("date", "unknown")
        if session_date and session_date != "unknown":
            report["by_date"][session_date]["sessions"] += 1
            report["by_date"][session_date]["duration"] += duration
            if task_analysis.get("likely_completed"):
                report["by_date"][session_date]["completed"] += 1

        # By actual outcome (now using expanded outcomes)
        outcome = task_analysis.get("outcome") or task_analysis.get("actual_outcome") or "unknown"
        report["by_outcome"][outcome] += 1

        # Collect confidence scores
        completion_analysis = session.get("completion_analysis", {})
        conf_score = completion_analysis.get("confidence_score")
        if conf_score is not None:
            confidence_scores.append(conf_score)

        # Tools usage
        for tool in stats.get("tools_used", []):
            report["tools_usage"][tool] += 1

        # Topics frequency
        for topic in task_analysis.get("key_topics", []):
            report["topics_frequency"][topic] += 1

        # JIRA tickets
        jira_ticket = task_analysis.get("jira_ticket")
        if jira_ticket:
            report["jira_tickets"][jira_ticket]["sessions"] += 1
            if task_analysis.get("likely_completed"):
                report["jira_tickets"][jira_ticket]["completed"] += 1

        # Successes
        for success in quality.get("successes", []):
            report["common_successes"][success["type"]] += 1

        # Claude Code features aggregation
        features = session.get("claude_code_features", {})

        # Skills
        skills = features.get("skills_invoked", [])
        if skills:
            report["claude_code_features"]["totals"]["sessions_using_skills"] += 1
            for skill in skills:
                skill_name = skill.get("skill", "unknown") if isinstance(skill, dict) else str(skill)
                report["claude_code_features"]["skills_usage"][skill_name] += 1
                report["claude_code_features"]["totals"]["total_skills_invoked"] += 1

        # Agents
        agents = features.get("agents_spawned", [])
        if agents:
            report["claude_code_features"]["totals"]["sessions_using_agents"] += 1
            for agent in agents:
                agent_type = agent.get("agent_type", "unknown") if isinstance(agent, dict) else str(agent)
                report["claude_code_features"]["agents_usage"][agent_type] += 1
                report["claude_code_features"]["totals"]["total_agents_spawned"] += 1

        # Slash commands
        slash_cmds = features.get("slash_commands", [])
        if slash_cmds:
            report["claude_code_features"]["totals"]["sessions_using_slash_commands"] += 1
            for cmd in slash_cmds:
                cmd_name = cmd.get("command", "unknown") if isinstance(cmd, dict) else str(cmd)
                report["claude_code_features"]["slash_commands_usage"][cmd_name] += 1
                report["claude_code_features"]["totals"]["total_slash_commands"] += 1

    # Convert defaultdicts to regular dicts and sort
    report["by_project"] = dict(report["by_project"])
    report["by_task_type"] = dict(report["by_task_type"])
    report["by_date"] = dict(sorted(report["by_date"].items()))
    report["by_outcome"] = dict(report["by_outcome"])
    report["tools_usage"] = dict(sorted(report["tools_usage"].items(), key=lambda x: -x[1]))
    report["topics_frequency"] = dict(sorted(report["topics_frequency"].items(), key=lambda x: -x[1]))
    report["jira_tickets"] = dict(report["jira_tickets"])
    report["common_issues"] = dict(sorted(report["common_issues"].items(), key=lambda x: -x[1]))
    report["common_successes"] = dict(sorted(report["common_successes"].items(), key=lambda x: -x[1]))

    # Convert Claude Code features defaultdicts
    report["claude_code_features"]["skills_usage"] = dict(
        sorted(report["claude_code_features"]["skills_usage"].items(), key=lambda x: -x[1])
    )
    report["claude_code_features"]["agents_usage"] = dict(
        sorted(report["claude_code_features"]["agents_usage"].items(), key=lambda x: -x[1])
    )
    report["claude_code_features"]["slash_commands_usage"] = dict(
        sorted(report["claude_code_features"]["slash_commands_usage"].items(), key=lambda x: -x[1])
    )

    # Calculate project-level metrics
    for project in report["by_project"]:
        proj_data = report["by_project"][project]
        proj_sessions = proj_data["sessions"]
        if proj_sessions > 0:
            proj_data["completion_rate"] = round(proj_data["completed"] / proj_sessions * 100, 1)
            proj_data["issue_rate"] = round(proj_data["with_issues"] / proj_sessions * 100, 1)
            proj_data["avg_duration"] = round(proj_data["duration"] / proj_sessions, 1)

    # Calculate averages and distributions
    n = len(valid_sessions)
    if n > 0:
        report["averages"] = {
            "avg_duration_minutes": round(report["summary"]["total_duration_minutes"] / n, 1),
            "avg_user_messages": round(report["summary"]["total_user_messages"] / n, 1),
            "avg_tool_calls": round(report["summary"]["total_tool_calls"] / n, 1),
            "avg_files_touched": round(report["summary"]["total_files_touched"] / n, 1),
            "completion_rate": round(report["sessions_completed"] / n * 100, 1),
            "issue_rate": round(report["sessions_with_issues"] / n * 100, 1)
        }

        # Duration distribution
        if durations:
            report["duration_distribution"] = {
                "min": round(min(durations), 1),
                "max": round(max(durations), 1),
                "median": round(statistics.median(durations), 1),
                "p25": round(calculate_percentile(durations, 25), 1),
                "p75": round(calculate_percentile(durations, 75), 1),
                "p90": round(calculate_percentile(durations, 90), 1),
                "std_dev": round(statistics.stdev(durations), 1) if len(durations) > 1 else 0
            }

            # Duration histogram with predefined buckets
            report["duration_histogram"] = calculate_duration_histogram(durations)

        # Tool calls distribution
        if tool_calls_list:
            report["tool_calls_distribution"] = {
                "min": min(tool_calls_list),
                "max": max(tool_calls_list),
                "median": round(statistics.median(tool_calls_list), 1),
                "p90": round(calculate_percentile(tool_calls_list, 90), 1)
            }

        # Files touched distribution
        if files_touched_list:
            report["files_touched_distribution"] = {
                "min": min(files_touched_list),
                "max": max(files_touched_list),
                "median": round(statistics.median(files_touched_list), 1),
                "p90": round(calculate_percentile(files_touched_list, 90), 1)
            }

        # Efficiency averages
        report["efficiency_averages"] = {}
        for key, values in efficiency_metrics.items():
            if values:
                report["efficiency_averages"][key] = {
                    "avg": round(statistics.mean(values), 2),
                    "median": round(statistics.median(values), 2)
                }

        # Completion confidence statistics
        if confidence_scores:
            report["completion_confidence"] = {
                "avg_score": round(statistics.mean(confidence_scores), 1),
                "median_score": round(statistics.median(confidence_scores), 1),
                "min_score": min(confidence_scores),
                "max_score": max(confidence_scores),
                "high_confidence_count": sum(1 for s in confidence_scores if s >= 70),
                "medium_confidence_count": sum(1 for s in confidence_scores if 40 <= s < 70),
                "low_confidence_count": sum(1 for s in confidence_scores if s < 40)
            }

        # Calculate expanded completion rate (includes completed, completed_with_issues, exploration_complete)
        successful_outcomes = ["completed", "completed_with_issues", "exploration_complete", "lookup_complete"]
        successful_count = sum(
            report["by_outcome"].get(outcome, 0)
            for outcome in successful_outcomes
        )
        report["averages"]["expanded_completion_rate"] = round(successful_count / n * 100, 1)

        # Add activity metrics (more reliable than heuristic completion detection)
        # These are observable facts, not inferred outcomes
        report["activity_metrics"] = {
            "sessions_with_edits": report["sessions_with_edits"],
            "sessions_with_edits_pct": round(report["sessions_with_edits"] / n * 100, 1),
            "sessions_with_commits": report["sessions_with_commits"],
            "sessions_with_commits_pct": round(report["sessions_with_commits"] / n * 100, 1),
            "sessions_with_tests": report["sessions_with_tests"],
            "sessions_with_tests_pct": round(report["sessions_with_tests"] / n * 100, 1),
            # Activity rate: sessions that produced tangible output (edits or commits)
            "activity_rate": round(
                (report["sessions_with_edits"] + report["sessions_with_commits"] -
                 # Avoid double counting sessions with both edits and commits
                 min(report["sessions_with_edits"], report["sessions_with_commits"]) * 0.5)
                / n * 100, 1
            ) if n > 0 else 0
        }

        # Completion signals breakdown (for transparency)
        report["completion_signals"] = {
            "positive": {
                "has_edits": report["sessions_with_edits"],
                "successful_commit": report["sessions_with_commits"],
                "tests_ran": report["sessions_with_tests"],
            },
            "negative": {
                "sessions_with_issues": report["sessions_with_issues"],
            }
        }

        # Calculate session type statistics
        for session_type in ["work", "lookup"]:
            st_data = report["by_session_type"][session_type]
            count = st_data["count"]
            if count > 0:
                st_data["pct"] = round(count / n * 100, 1)
                st_data["avg_duration"] = round(st_data["total_duration"] / count, 1)
                st_data["avg_tool_calls"] = round(st_data["total_tool_calls"] / count, 1)
            else:
                st_data["pct"] = 0
                st_data["avg_duration"] = 0
                st_data["avg_tool_calls"] = 0

    return report


def print_report(report: Dict):
    """Print a human-readable summary of the report."""
    print("\n" + "="*70)
    print("CLAUDE CODE USAGE ANALYSIS REPORT")
    print("="*70)

    summary = report["summary"]
    print(f"\n{'='*30} OVERALL SUMMARY {'='*30}")
    print(f"   Total sessions analyzed: {summary['total_sessions']}")
    print(f"   Valid sessions: {summary['valid_sessions']} ({summary['invalid_sessions']} filtered out)")
    print(f"   Total time: {summary['total_duration_minutes']:.0f} minutes ({summary['total_duration_minutes']/60:.1f} hours)")
    print(f"   Total user messages: {summary['total_user_messages']}")
    print(f"   Total assistant messages: {summary['total_assistant_messages']}")
    print(f"   Total tool calls: {summary['total_tool_calls']}")
    print(f"   Total files touched: {summary['total_files_touched']}")

    if "averages" in report:
        avg = report["averages"]
        print(f"\n{'='*30} AVERAGES PER SESSION {'='*25}")
        print(f"   Avg duration: {avg['avg_duration_minutes']} minutes")
        print(f"   Avg user messages: {avg['avg_user_messages']}")
        print(f"   Avg tool calls: {avg['avg_tool_calls']}")
        print(f"   Avg files touched: {avg['avg_files_touched']}")
        print(f"   Completion rate: {avg['completion_rate']}%")
        print(f"   Sessions with issues: {avg['issue_rate']}%")

    if "duration_distribution" in report:
        dist = report["duration_distribution"]
        print(f"\n{'='*30} DURATION DISTRIBUTION {'='*24}")
        print(f"   Min: {dist['min']} min | Max: {dist['max']} min")
        print(f"   Median: {dist['median']} min | Std Dev: {dist['std_dev']} min")
        print(f"   P25: {dist['p25']} min | P75: {dist['p75']} min | P90: {dist['p90']} min")

    if "by_outcome" in report:
        print(f"\n{'='*30} BY OUTCOME {'='*35}")
        for outcome, count in report["by_outcome"].items():
            pct = round(count / summary['valid_sessions'] * 100, 1) if summary['valid_sessions'] > 0 else 0
            print(f"   {outcome}: {count} ({pct}%)")

    print(f"\n{'='*30} BY PROJECT {'='*35}")
    print(f"   {'Project':<15} {'Sessions':>8} {'Complete':>8} {'Rate':>6} {'Issues':>6} {'Avg Min':>8}")
    print(f"   {'-'*15} {'-'*8} {'-'*8} {'-'*6} {'-'*6} {'-'*8}")
    for project, data in sorted(report["by_project"].items(), key=lambda x: -x[1]["sessions"]):
        comp_rate = data.get('completion_rate', 0)
        issue_rate = data.get('issue_rate', 0)
        avg_dur = data.get('avg_duration', 0)
        print(f"   {project:<15} {data['sessions']:>8} {data['completed']:>8} {comp_rate:>5.1f}% {issue_rate:>5.1f}% {avg_dur:>8.1f}")

    print(f"\n{'='*30} BY TASK TYPE {'='*32}")
    for task_type, count in sorted(report["by_task_type"].items(), key=lambda x: -x[1]):
        pct = round(count / summary['valid_sessions'] * 100, 1) if summary['valid_sessions'] > 0 else 0
        print(f"   {task_type}: {count} ({pct}%)")

    if report.get("by_date"):
        print(f"\n{'='*30} TIME SERIES (BY DATE) {'='*24}")
        for date, data in list(report["by_date"].items())[-10:]:  # Last 10 days
            rate = round(data['completed'] / data['sessions'] * 100, 1) if data['sessions'] > 0 else 0
            print(f"   {date}: {data['sessions']} sessions, {data['completed']} completed ({rate}%)")

    print(f"\n{'='*30} TOP 10 TOOLS USED {'='*28}")
    for tool, count in list(report["tools_usage"].items())[:10]:
        print(f"   {tool}: {count}")

    if report.get("topics_frequency"):
        print(f"\n{'='*30} TOP TOPICS {'='*35}")
        for topic, count in list(report["topics_frequency"].items())[:10]:
            print(f"   {topic}: {count}")

    if report.get("jira_tickets"):
        print(f"\n{'='*30} JIRA TICKETS {'='*32}")
        sorted_tickets = sorted(report["jira_tickets"].items(), key=lambda x: -x[1]["sessions"])
        for ticket, data in sorted_tickets[:10]:
            rate = round(data['completed'] / data['sessions'] * 100, 1) if data['sessions'] > 0 else 0
            print(f"   {ticket}: {data['sessions']} sessions, {data['completed']} completed ({rate}%)")

    if report.get("efficiency_averages"):
        print(f"\n{'='*30} EFFICIENCY METRICS {'='*27}")
        for metric, values in report["efficiency_averages"].items():
            print(f"   {metric}: avg={values['avg']}, median={values['median']}")

    if report["common_issues"]:
        print(f"\n{'='*30} COMMON ISSUES {'='*31}")
        for issue, count in report["common_issues"].items():
            print(f"   {issue}: {count} occurrences")

    if report["common_successes"]:
        print(f"\n{'='*30} COMMON SUCCESSES {'='*28}")
        for success, count in report["common_successes"].items():
            print(f"   {success}: {count} occurrences")

    # Claude Code Features
    features = report.get("claude_code_features", {})
    totals = features.get("totals", {})
    if any(totals.get(k, 0) > 0 for k in totals):
        print(f"\n{'='*30} CLAUDE CODE FEATURES {'='*24}")

        # Summary
        print(f"\n   --- Feature Usage Summary ---")
        print(f"   Skills invoked: {totals.get('total_skills_invoked', 0)} (in {totals.get('sessions_using_skills', 0)} sessions)")
        print(f"   Agents spawned: {totals.get('total_agents_spawned', 0)} (in {totals.get('sessions_using_agents', 0)} sessions)")
        print(f"   Slash commands: {totals.get('total_slash_commands', 0)} (in {totals.get('sessions_using_slash_commands', 0)} sessions)")

        # Skills breakdown
        skills = features.get("skills_usage", {})
        if skills:
            print(f"\n   --- Skills Usage ---")
            for skill, count in list(skills.items())[:10]:
                print(f"   /{skill}: {count}")

        # Agents breakdown
        agents = features.get("agents_usage", {})
        if agents:
            print(f"\n   --- Agents Spawned ---")
            for agent, count in list(agents.items())[:10]:
                print(f"   {agent}: {count}")

        # Slash commands breakdown
        slash_cmds = features.get("slash_commands_usage", {})
        if slash_cmds:
            print(f"\n   --- Slash Commands ---")
            for cmd, count in list(slash_cmds.items())[:10]:
                print(f"   /{cmd}: {count}")

    print("\n" + "="*70)


def main():
    parser = argparse.ArgumentParser(description="Analyze extracted Claude Code sessions")
    parser.add_argument("--input", type=str, default=None,
                        help="Input file (auto-detects format: extract_sessions.py output or report_data JSON)")
    parser.add_argument("--output", type=str, default="session_analysis.json",
                        help="Output analysis file")
    parser.add_argument("--report", type=str, default="aggregate_report.json",
                        help="Aggregate report file")
    parser.add_argument("--auto", action="store_true",
                        help="Auto-detect latest report_data file")
    args = parser.parse_args()

    # Determine input file
    input_path = None

    if args.input:
        input_path = Path(args.input)
    elif args.auto:
        # Auto-detect latest report_data file
        latest = find_latest_report_data(".")
        if latest:
            input_path = Path(latest)
            print(f"Auto-detected input file: {input_path}")
    else:
        # Try default locations in order
        default_paths = [
            "reports/data/report_data_*.json",  # Glob pattern for report_data
            "sessions_last_7_days.json",
            "session_analysis.json"
        ]
        for pattern in default_paths:
            if "*" in pattern:
                matches = sorted(glob_module.glob(pattern))
                if matches:
                    input_path = Path(matches[-1])  # Latest file
                    break
            elif Path(pattern).exists():
                input_path = Path(pattern)
                break

    if not input_path or not input_path.exists():
        print("Error: No input file found.")
        print("Options:")
        print("  --input <file>  : Specify input file directly")
        print("  --auto          : Auto-detect latest report_data file")
        print("\nSupported formats:")
        print("  - extract_sessions.py output (sessions_last_7_days.json)")
        print("  - generate_report.py output (reports/data/report_data_*.json)")
        return

    # Load and normalize sessions
    try:
        sessions, input_format = load_sessions(str(input_path))
        print(f"Loaded {len(sessions)} sessions from {input_path}")
        print(f"Detected format: {input_format}")
    except Exception as e:
        print(f"Error loading sessions: {e}")
        return

    # Analyze each session
    analyzed_sessions = []
    for i, session in enumerate(sessions):
        session_id = session.get('session_id', 'unknown')[:8]
        print(f"Analyzing {i+1}/{len(sessions)}: {session_id}...")
        try:
            analyzed = analyze_session(session)
            analyzed_sessions.append(analyzed)
        except Exception as e:
            print(f"  Warning: Failed to analyze session {session_id}: {e}")

    if not analyzed_sessions:
        print("Error: No sessions could be analyzed.")
        return

    # Save individual session analyses
    with open(args.output, 'w') as f:
        json.dump(analyzed_sessions, f, indent=2, default=str)
    print(f"\nSession analyses saved to: {args.output}")

    # Generate and save aggregate report
    report = generate_aggregate_report(analyzed_sessions)

    # Add input metadata to report
    report["_input_metadata"] = {
        "input_file": str(input_path),
        "input_format": input_format,
        "total_sessions_loaded": len(sessions),
        "sessions_analyzed": len(analyzed_sessions),
        "analysis_timestamp": datetime.now().isoformat()
    }

    with open(args.report, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    print(f"Aggregate report saved to: {args.report}")

    # Print summary
    print_report(report)


if __name__ == "__main__":
    main()
