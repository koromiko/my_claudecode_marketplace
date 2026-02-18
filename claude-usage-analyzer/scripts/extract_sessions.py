#!/usr/bin/env python3
"""
Claude Code Session Extractor and Analyzer

This script extracts conversation sessions from Claude Code's storage
and generates structured summaries for analysis.
"""

import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any, Optional
import argparse


class SessionExtractor:
    def __init__(self, claude_dir: str = None):
        self.claude_dir = Path(claude_dir or os.path.expanduser("~/.claude"))
        self.projects_dir = self.claude_dir / "projects"

    def get_all_sessions(self, days_back: int = None, project_filter: str = None) -> List[Dict]:
        """Get all session files, optionally filtered by date or project."""
        sessions = []

        if not self.projects_dir.exists():
            print(f"Projects directory not found: {self.projects_dir}")
            return sessions

        cutoff_date = None
        if days_back:
            cutoff_date = datetime.now() - timedelta(days=days_back)

        for project_dir in self.projects_dir.iterdir():
            if not project_dir.is_dir():
                continue

            project_name = self._decode_project_name(project_dir.name)

            if project_filter and project_filter.lower() not in project_name.lower():
                continue

            for session_file in project_dir.glob("*.jsonl"):
                # Skip agent sub-sessions
                if session_file.name.startswith("agent-"):
                    continue

                # Check file modification time for date filter
                if cutoff_date:
                    mtime = datetime.fromtimestamp(session_file.stat().st_mtime)
                    if mtime < cutoff_date:
                        continue

                sessions.append({
                    "file_path": session_file,
                    "project_name": project_name,
                    "session_id": session_file.stem,
                    "modified_time": datetime.fromtimestamp(session_file.stat().st_mtime)
                })

        return sorted(sessions, key=lambda x: x["modified_time"], reverse=True)

    def _decode_project_name(self, encoded_name: str) -> str:
        """Convert encoded project directory name back to readable path."""
        return encoded_name.replace("-", "/")

    def parse_session(self, session_info: Dict) -> Dict:
        """Parse a single session file and extract structured data."""
        session_data = {
            "session_id": session_info["session_id"],
            "project": session_info["project_name"],
            "file_path": str(session_info["file_path"]),
            "metadata": {
                "start_time": None,
                "end_time": None,
                "duration_minutes": 0,
                "git_branch": None,
                "claude_version": None
            },
            "statistics": {
                "user_messages": 0,
                "assistant_messages": 0,
                "total_turns": 0,
                "tools_used": set(),
                "tool_call_count": 0
            },
            "claude_code_features": {
                "skills_invoked": [],      # Skill tool calls with skill name
                "agents_spawned": [],      # Task tool calls with subagent_type
                "slash_commands": []       # User messages starting with /
            },
            "messages": [],
            "user_prompts": [],
            "assistant_responses": [],
            "errors": [],
            "files_touched": set(),
            "commands_run": []
        }

        try:
            with open(session_info["file_path"], 'r') as f:
                for line in f:
                    try:
                        msg = json.loads(line.strip())
                        self._process_message(msg, session_data)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            session_data["errors"].append(f"Error reading file: {str(e)}")

        # Post-process
        self._finalize_session_data(session_data)

        return session_data

    def _process_message(self, msg: Dict, session_data: Dict):
        """Process a single message and update session data."""
        msg_type = msg.get("type")
        timestamp = msg.get("timestamp")

        if timestamp:
            ts = self._parse_timestamp(timestamp)
            if ts:
                if session_data["metadata"]["start_time"] is None:
                    session_data["metadata"]["start_time"] = ts
                session_data["metadata"]["end_time"] = ts

        # Extract metadata
        if msg.get("gitBranch"):
            session_data["metadata"]["git_branch"] = msg["gitBranch"]
        if msg.get("version"):
            session_data["metadata"]["claude_version"] = msg["version"]

        # Store the complete raw message
        session_data["messages"].append(msg)

        if msg_type == "user":
            session_data["statistics"]["user_messages"] += 1
            raw_content = msg.get("message", {}).get("content", "")

            # Extract text content - handle both string and list formats
            if isinstance(raw_content, str):
                text_content = raw_content
            elif isinstance(raw_content, list):
                # Extract text from text blocks in the content list
                text_parts = []
                for block in raw_content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif isinstance(block, str):
                        text_parts.append(block)
                text_content = "\n".join(text_parts)
            else:
                text_content = ""

            if text_content and not msg.get("isMeta"):
                # Track slash commands (user-invoked commands starting with /)
                if text_content.strip().startswith("/"):
                    cmd_match = re.match(r'^/(\S+)', text_content.strip())
                    if cmd_match:
                        session_data["claude_code_features"]["slash_commands"].append({
                            "command": cmd_match.group(1),
                            "timestamp": timestamp
                        })
                # Clean up command messages
                if "<command-name>" not in text_content:
                    session_data["user_prompts"].append({
                        "timestamp": timestamp,
                        "content": text_content,  # Full content, no truncation
                        "has_todos": bool(msg.get("todos"))
                    })

        elif msg_type == "assistant":
            session_data["statistics"]["assistant_messages"] += 1
            message = msg.get("message", {})
            content = message.get("content", [])

            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "tool_use":
                            tool_name = block.get("name", "unknown")
                            session_data["statistics"]["tools_used"].add(tool_name)
                            session_data["statistics"]["tool_call_count"] += 1

                            # Track file operations
                            tool_input = block.get("input", {})
                            if tool_name in ["Read", "Edit", "Write"]:
                                file_path = tool_input.get("file_path")
                                if file_path:
                                    session_data["files_touched"].add(file_path)
                            elif tool_name == "Bash":
                                cmd = tool_input.get("command", "")
                                if cmd:
                                    session_data["commands_run"].append(cmd)  # Full command

                            # Track Claude Code features
                            elif tool_name == "Skill":
                                skill_name = tool_input.get("skill", "unknown")
                                session_data["claude_code_features"]["skills_invoked"].append({
                                    "skill": skill_name,
                                    "args": tool_input.get("args"),
                                    "timestamp": timestamp
                                })
                            elif tool_name == "Task":
                                subagent_type = tool_input.get("subagent_type", "unknown")
                                session_data["claude_code_features"]["agents_spawned"].append({
                                    "agent_type": subagent_type,
                                    "description": tool_input.get("description", ""),
                                    "timestamp": timestamp
                                })

                        elif block.get("type") == "text":
                            text = block.get("text", "")
                            if text:
                                session_data["assistant_responses"].append({
                                    "timestamp": timestamp,
                                    "content": text  # Full content, no truncation
                                })
            elif isinstance(content, str) and content:
                session_data["assistant_responses"].append({
                    "timestamp": timestamp,
                    "content": content  # Full content, no truncation
                })

        elif msg_type == "summary":
            session_data["summary"] = msg.get("summary", "")

        elif msg_type == "tool_result":
            # Track tool results for completeness
            session_data["statistics"]["tool_call_count"] += 0  # Already counted in tool_use

    def _parse_timestamp(self, ts) -> Optional[datetime]:
        """Parse various timestamp formats."""
        if isinstance(ts, (int, float)):
            # Unix timestamp in milliseconds
            return datetime.fromtimestamp(ts / 1000)
        elif isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except:
                return None
        return None

    def _finalize_session_data(self, session_data: Dict):
        """Finalize and clean up session data."""
        # Calculate duration
        if session_data["metadata"]["start_time"] and session_data["metadata"]["end_time"]:
            start = session_data["metadata"]["start_time"]
            end = session_data["metadata"]["end_time"]
            if isinstance(start, datetime) and isinstance(end, datetime):
                duration = (end - start).total_seconds() / 60
                session_data["metadata"]["duration_minutes"] = round(duration, 1)

        # Convert sets to lists for JSON serialization
        session_data["statistics"]["tools_used"] = list(session_data["statistics"]["tools_used"])
        session_data["files_touched"] = list(session_data["files_touched"])

        # Calculate total turns
        session_data["statistics"]["total_turns"] = (
            session_data["statistics"]["user_messages"] +
            session_data["statistics"]["assistant_messages"]
        )

        # Convert datetime to string
        for key in ["start_time", "end_time"]:
            val = session_data["metadata"][key]
            if isinstance(val, datetime):
                session_data["metadata"][key] = val.isoformat()


def generate_summary_for_analysis(session_data: Dict, include_messages: bool = False) -> Dict:
    """
    Generate a condensed summary suitable for AI analysis.
    This format is designed for further processing to identify
    what went well, what went badly, and improvements.

    Args:
        session_data: The parsed session data
        include_messages: If True, include all raw messages in output
    """
    # Get first few user prompts to understand the task
    initial_prompts = session_data.get("user_prompts", [])[:5]
    prompt_texts = [p.get("content", "")[:500] for p in initial_prompts]

    # Get a sample of assistant responses
    responses = session_data.get("assistant_responses", [])
    response_samples = [r.get("content", "")[:500] for r in responses[:3]]

    # Identify potential issues
    potential_issues = []
    commands = session_data.get("commands_run", [])
    for cmd in commands:
        if any(err in cmd.lower() for err in ["error", "fail", "fix", "debug"]):
            potential_issues.append(cmd)

    result = {
        "session_id": session_data["session_id"],
        "project": session_data["project"],
        "metadata": session_data["metadata"],
        "statistics": session_data["statistics"],
        "claude_code_features": session_data.get("claude_code_features", {}),
        "task_context": {
            "initial_prompts": prompt_texts,
            "response_samples": response_samples,
            "files_touched": session_data.get("files_touched", [])[:20],
            "commands_sample": commands[:10],
            "potential_issues": potential_issues[:5]
        },
        "existing_summary": session_data.get("summary", ""),
        "analysis_needed": True
    }

    # Optionally include all raw messages
    if include_messages:
        result["messages"] = session_data.get("messages", [])

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Extract Claude Code sessions for analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract last 7 days with summaries only (default)
  python extract_sessions.py

  # Extract with all raw messages included
  python extract_sessions.py --messages

  # Extract full session data (all fields, no summarization)
  python extract_sessions.py --full

  # Extract specific project with messages
  python extract_sessions.py --project myapp --messages --days 30
        """
    )
    parser.add_argument("--days", type=int, default=7, help="Number of days back to analyze")
    parser.add_argument("--project", type=str, help="Filter by project name (partial match)")
    parser.add_argument("--output", type=str, default="sessions_extract.json", help="Output file")
    parser.add_argument("--full", action="store_true", help="Include full session data (all fields, no summarization)")
    parser.add_argument("--messages", action="store_true", help="Include all raw messages in output")
    args = parser.parse_args()

    extractor = SessionExtractor()

    print(f"Extracting sessions from last {args.days} days...")
    if args.project:
        print(f"Filtering by project: {args.project}")
    if args.messages:
        print("Including all raw messages")
    if args.full:
        print("Full session data mode (no summarization)")

    sessions = extractor.get_all_sessions(days_back=args.days, project_filter=args.project)
    print(f"Found {len(sessions)} sessions")

    results = []
    for i, session_info in enumerate(sessions):
        print(f"Processing {i+1}/{len(sessions)}: {session_info['session_id'][:8]}... ({session_info['project_name']})")

        session_data = extractor.parse_session(session_info)

        if args.full:
            results.append(session_data)
        else:
            results.append(generate_summary_for_analysis(session_data, include_messages=args.messages))

    # Save results
    output_path = Path(args.output)
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\nResults saved to: {output_path}")
    print(f"Total sessions extracted: {len(results)}")

    # Print summary statistics
    total_user_msgs = sum(s.get("statistics", {}).get("user_messages", 0) for s in results)
    total_assistant_msgs = sum(s.get("statistics", {}).get("assistant_messages", 0) for s in results)
    total_tool_calls = sum(s.get("statistics", {}).get("tool_call_count", 0) for s in results)

    print(f"\nAggregate Statistics:")
    print(f"  Total user messages: {total_user_msgs}")
    print(f"  Total assistant messages: {total_assistant_msgs}")
    print(f"  Total tool calls: {total_tool_calls}")


if __name__ == "__main__":
    main()
