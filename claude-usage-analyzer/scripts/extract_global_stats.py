#!/usr/bin/env python3
"""
Claude Code Global Stats Extractor

This script extracts global usage statistics from ~/.claude.json,
including skill usage, startup counts, and per-project cumulative stats.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional


class GlobalStatsExtractor:
    """Extracts global stats from ~/.claude.json"""

    def __init__(self, claude_json_path: str = None):
        self.claude_json_path = Path(
            claude_json_path or os.path.expanduser("~/.claude.json")
        )
        self._data = None

    def _load_data(self) -> Dict:
        """Load and cache the claude.json data."""
        if self._data is None:
            if not self.claude_json_path.exists():
                self._data = {}
            else:
                try:
                    with open(self.claude_json_path, 'r') as f:
                        self._data = json.load(f)
                except (json.JSONDecodeError, IOError) as e:
                    print(f"Warning: Could not load {self.claude_json_path}: {e}")
                    self._data = {}
        return self._data

    def get_global_stats(self) -> Dict[str, Any]:
        """Extract global usage statistics."""
        data = self._load_data()

        # Parse first start time
        first_start = data.get("firstStartTime")
        if first_start:
            try:
                first_start_dt = datetime.fromisoformat(first_start.replace("Z", "+00:00"))
                days_since_first_use = (datetime.now(first_start_dt.tzinfo) - first_start_dt).days
            except (ValueError, TypeError):
                days_since_first_use = None
        else:
            days_since_first_use = None

        return {
            "num_startups": data.get("numStartups", 0),
            "prompt_queue_use_count": data.get("promptQueueUseCount", 0),
            "first_start_time": first_start,
            "days_since_first_use": days_since_first_use,
            "install_method": data.get("installMethod", "unknown"),
            "auto_updates_enabled": data.get("autoUpdates", False),
            "auto_compact_enabled": data.get("autoCompactEnabled", False),
            "has_completed_onboarding": data.get("hasCompletedOnboarding", False),
            "last_onboarding_version": data.get("lastOnboardingVersion"),
            "last_release_notes_seen": data.get("lastReleaseNotesSeen"),
        }

    def get_skill_usage(self) -> Dict[str, Any]:
        """Extract skill usage statistics."""
        data = self._load_data()
        skill_usage = data.get("skillUsage", {})

        skills = []
        total_usage = 0

        for skill_name, usage_data in skill_usage.items():
            count = usage_data.get("usageCount", 0)
            last_used = usage_data.get("lastUsedAt")

            # Convert timestamp to ISO format
            if last_used:
                try:
                    last_used_dt = datetime.fromtimestamp(last_used / 1000)
                    last_used_iso = last_used_dt.isoformat()
                except (ValueError, TypeError, OSError):
                    last_used_iso = None
            else:
                last_used_iso = None

            skills.append({
                "skill": skill_name,
                "usage_count": count,
                "last_used_at": last_used_iso,
            })
            total_usage += count

        # Sort by usage count descending
        skills.sort(key=lambda x: x["usage_count"], reverse=True)

        return {
            "total_skill_invocations": total_usage,
            "unique_skills_used": len(skills),
            "skills": skills,
        }

    def get_tips_history(self) -> Dict[str, Any]:
        """Extract tips history (which features user has been introduced to)."""
        data = self._load_data()
        tips = data.get("tipsHistory", {})

        # Count tips by category
        categories = {
            "keyboard_shortcuts": [],
            "features": [],
            "integrations": [],
            "other": []
        }

        for tip_name, count in tips.items():
            tip_info = {"tip": tip_name, "shown_count": count}

            # Categorize tips
            if any(k in tip_name.lower() for k in ["shift", "enter", "tab", "esc", "hotkey", "keybinding"]):
                categories["keyboard_shortcuts"].append(tip_info)
            elif any(k in tip_name.lower() for k in ["ide", "vscode", "cursor", "github", "slack", "install"]):
                categories["integrations"].append(tip_info)
            elif any(k in tip_name.lower() for k in ["command", "mode", "memory", "todo", "agent", "permission"]):
                categories["features"].append(tip_info)
            else:
                categories["other"].append(tip_info)

        return {
            "total_tips_shown": sum(tips.values()),
            "unique_tips": len(tips),
            "tips_by_category": categories,
        }

    def get_project_stats(self, project_filter: str = None) -> Dict[str, Any]:
        """
        Extract per-project statistics from ~/.claude.json.
        Note: These are "last session" stats per project, not cumulative.

        Args:
            project_filter: Optional filter to match project paths (partial match)
        """
        data = self._load_data()
        projects = data.get("projects", {})

        project_stats = []
        total_cost = 0
        total_tokens_in = 0
        total_tokens_out = 0
        total_lines_added = 0
        total_lines_removed = 0

        for project_path, project_data in projects.items():
            # Apply filter if provided
            if project_filter and project_filter.lower() not in project_path.lower():
                continue

            # Extract last session stats
            cost = project_data.get("lastCost", 0)
            tokens_in = project_data.get("lastTotalInputTokens", 0)
            tokens_out = project_data.get("lastTotalOutputTokens", 0)
            cache_creation = project_data.get("lastTotalCacheCreationInputTokens", 0)
            cache_read = project_data.get("lastTotalCacheReadInputTokens", 0)
            lines_added = project_data.get("lastLinesAdded", 0)
            lines_removed = project_data.get("lastLinesRemoved", 0)
            duration = project_data.get("lastDuration", 0)
            api_duration = project_data.get("lastAPIDuration", 0)
            tool_duration = project_data.get("lastToolDuration", 0)

            # Get model usage breakdown
            model_usage = project_data.get("lastModelUsage", {})

            # Extract project name from path
            project_name = project_path.split("/")[-1] if "/" in project_path else project_path

            project_stats.append({
                "project_path": project_path,
                "project_name": project_name,
                "last_session_id": project_data.get("lastSessionId"),
                "last_cost_usd": round(cost, 4) if cost else 0,
                "last_tokens": {
                    "input": tokens_in,
                    "output": tokens_out,
                    "cache_creation": cache_creation,
                    "cache_read": cache_read,
                },
                "last_code_changes": {
                    "lines_added": lines_added,
                    "lines_removed": lines_removed,
                },
                "last_durations_ms": {
                    "total": duration,
                    "api": api_duration,
                    "tool": tool_duration,
                },
                "model_usage": model_usage,
                "has_trust_accepted": project_data.get("hasTrustDialogAccepted", False),
                "onboarding_count": project_data.get("projectOnboardingSeenCount", 0),
            })

            # Aggregate totals (note: these are "last" values, not true cumulative)
            total_cost += cost
            total_tokens_in += tokens_in
            total_tokens_out += tokens_out
            total_lines_added += lines_added
            total_lines_removed += lines_removed

        # Sort by cost descending
        project_stats.sort(key=lambda x: x["last_cost_usd"], reverse=True)

        return {
            "total_projects": len(project_stats),
            "projects_with_sessions": len([p for p in project_stats if p["last_session_id"]]),
            "aggregate_last_session_stats": {
                "total_cost_usd": round(total_cost, 2),
                "total_input_tokens": total_tokens_in,
                "total_output_tokens": total_tokens_out,
                "total_lines_added": total_lines_added,
                "total_lines_removed": total_lines_removed,
            },
            "projects": project_stats,
        }

    def get_all_stats(self, project_filter: str = None) -> Dict[str, Any]:
        """Get all available statistics from ~/.claude.json."""
        return {
            "source": str(self.claude_json_path),
            "extracted_at": datetime.now().isoformat(),
            "global_stats": self.get_global_stats(),
            "skill_usage": self.get_skill_usage(),
            "tips_history": self.get_tips_history(),
            "project_stats": self.get_project_stats(project_filter),
        }


def main():
    """CLI entry point for standalone testing."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract global stats from ~/.claude.json"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="global_stats.json",
        help="Output file path (default: global_stats.json)"
    )
    parser.add_argument(
        "--project",
        type=str,
        help="Filter projects by name (partial match)"
    )
    parser.add_argument(
        "--skills-only",
        action="store_true",
        help="Only output skill usage data"
    )

    args = parser.parse_args()

    extractor = GlobalStatsExtractor()

    if args.skills_only:
        stats = extractor.get_skill_usage()
    else:
        stats = extractor.get_all_stats(project_filter=args.project)

    # Output
    output_path = Path(args.output)
    with open(output_path, 'w') as f:
        json.dump(stats, f, indent=2)

    print(f"Stats extracted to: {output_path}")

    # Print summary
    if not args.skills_only:
        global_stats = stats.get("global_stats", {})
        skill_usage = stats.get("skill_usage", {})
        project_stats = stats.get("project_stats", {})

        print(f"\nSummary:")
        print(f"  Total startups: {global_stats.get('num_startups', 0)}")
        print(f"  Days since first use: {global_stats.get('days_since_first_use', 'N/A')}")
        print(f"  Prompt queue uses: {global_stats.get('prompt_queue_use_count', 0)}")
        print(f"  Total skill invocations: {skill_usage.get('total_skill_invocations', 0)}")
        print(f"  Unique skills used: {skill_usage.get('unique_skills_used', 0)}")
        print(f"  Total projects: {project_stats.get('total_projects', 0)}")
    else:
        print(f"\nSkill Usage Summary:")
        print(f"  Total invocations: {stats.get('total_skill_invocations', 0)}")
        print(f"  Unique skills: {stats.get('unique_skills_used', 0)}")
        if stats.get("skills"):
            print(f"  Top skills:")
            for skill in stats["skills"][:5]:
                print(f"    - {skill['skill']}: {skill['usage_count']} uses")


if __name__ == "__main__":
    main()
