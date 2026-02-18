#!/usr/bin/env python3
"""
Prepare data for qualitative analysis of Claude Code sessions.
Extracts meaningful sessions and generates prompts for analysis.
"""

import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime


def load_report(input_path: str) -> Dict:
    """Load the report data file."""
    with open(input_path, 'r') as f:
        return json.load(f)


def extract_sessions_with_issues(sessions: List[Dict]) -> List[Dict]:
    """Extract sessions that had issues for analysis."""
    return [
        {
            "session_id": s.get("session_id"),
            "session_id_short": s.get("session_id_short", s.get("session_id", "")[:8]),
            "session_file_path": s.get("session_file_path", ""),
            "project": s.get("project"),
            "date": s.get("date"),
            "duration_minutes": s.get("duration_minutes"),
            "task_summary": s.get("task_summary", "")[:500],  # Truncate long summaries
            "task_type": s.get("task_type"),
            "issues": s.get("issues", []),
            "outcome": s.get("outcome"),
            "tools_used": s.get("stats", {}).get("tools_used", []),
            "key_topics": s.get("key_topics", []),
            "ai_summary": s.get("ai_summary", ""),
            "conversation_samples": s.get("conversation_samples", {}),
            "claude_code_features": s.get("claude_code_features", {})
        }
        for s in sessions
        if s.get("issues") and len(s.get("issues", [])) > 0
    ]


def extract_successful_sessions(sessions: List[Dict]) -> List[Dict]:
    """Extract sessions that completed successfully.

    Now includes expanded successful outcomes:
    - completed
    - completed_with_issues
    - exploration_complete
    """
    successful_outcomes = ["completed", "completed_with_issues", "exploration_complete"]
    return [
        {
            "session_id": s.get("session_id"),
            "session_id_short": s.get("session_id_short", s.get("session_id", "")[:8]),
            "session_file_path": s.get("session_file_path", ""),
            "project": s.get("project"),
            "date": s.get("date"),
            "duration_minutes": s.get("duration_minutes"),
            "task_summary": s.get("task_summary", "")[:500],
            "task_type": s.get("task_type"),
            "successes": s.get("successes", []),
            "outcome": s.get("outcome"),
            "completion_confidence": s.get("completion_confidence"),
            "confidence_assessment": s.get("confidence_assessment"),
            "tools_used": s.get("stats", {}).get("tools_used", []),
            "files_touched": s.get("stats", {}).get("files_touched", 0),
            "key_topics": s.get("key_topics", []),
            "ai_summary": s.get("ai_summary", ""),
            "conversation_samples": s.get("conversation_samples", {}),
            "claude_code_features": s.get("claude_code_features", {})
        }
        for s in sessions
        if s.get("outcome") in successful_outcomes
    ]


def extract_abandoned_sessions(sessions: List[Dict]) -> List[Dict]:
    """Extract sessions that were abandoned or blocked."""
    abandoned_outcomes = ["abandoned", "blocked"]
    return [
        {
            "session_id": s.get("session_id"),
            "session_id_short": s.get("session_id_short", s.get("session_id", "")[:8]),
            "session_file_path": s.get("session_file_path", ""),
            "project": s.get("project"),
            "date": s.get("date"),
            "duration_minutes": s.get("duration_minutes"),
            "task_summary": s.get("task_summary", "")[:500],
            "task_type": s.get("task_type"),
            "outcome": s.get("outcome"),
            "completion_confidence": s.get("completion_confidence"),
            "confidence_assessment": s.get("confidence_assessment"),
            "issues": s.get("issues", []),
            "tools_used": s.get("stats", {}).get("tools_used", []),
            "tool_calls": s.get("stats", {}).get("tool_calls", 0),
            "key_topics": s.get("key_topics", []),
            "ai_summary": s.get("ai_summary", ""),
            "conversation_samples": s.get("conversation_samples", {}),
            "claude_code_features": s.get("claude_code_features", {})
        }
        for s in sessions
        if s.get("outcome") in abandoned_outcomes
    ]


def extract_long_running_sessions(sessions: List[Dict], threshold_minutes: float = 60) -> List[Dict]:
    """Extract long-running sessions (>60 minutes by default).

    Note: Renamed from 'high_effort_sessions' for clarity. These are sessions
    that ran for an extended duration, which may indicate complex tasks,
    investigation work, or potential inefficiencies.

    Args:
        sessions: List of session dictionaries
        threshold_minutes: Duration threshold in minutes (default: 60)

    Returns:
        List of sessions exceeding the duration threshold
    """
    return [
        {
            "session_id": s.get("session_id"),
            "session_id_short": s.get("session_id_short", s.get("session_id", "")[:8]),
            "session_file_path": s.get("session_file_path", ""),
            "project": s.get("project"),
            "date": s.get("date"),
            "duration_minutes": s.get("duration_minutes"),
            "task_summary": s.get("task_summary", "")[:500],
            "task_type": s.get("task_type"),
            "outcome": s.get("outcome"),
            "user_messages": s.get("stats", {}).get("user_messages", 0),
            "tool_calls": s.get("stats", {}).get("tool_calls", 0),
            "files_touched": s.get("stats", {}).get("files_touched", 0),
            "issues": s.get("issues", []),
            "successes": s.get("successes", []),
            "ai_summary": s.get("ai_summary", ""),
            "conversation_samples": s.get("conversation_samples", {}),
            "claude_code_features": s.get("claude_code_features", {})
        }
        for s in sessions
        if s.get("duration_minutes", 0) > threshold_minutes
    ]


# Alias for backward compatibility
def extract_high_effort_sessions(sessions: List[Dict], threshold_minutes: float = 60) -> List[Dict]:
    """Deprecated: Use extract_long_running_sessions instead."""
    return extract_long_running_sessions(sessions, threshold_minutes)


def extract_task_summaries_by_type(sessions: List[Dict]) -> Dict[str, List[str]]:
    """Group non-empty task summaries by task type."""
    summaries: Dict[str, List[str]] = {}
    for s in sessions:
        task_type = s.get("task_type", "unknown")
        summary = s.get("task_summary", "").strip()
        if summary and len(summary) > 20:  # Filter out very short summaries
            if task_type not in summaries:
                summaries[task_type] = []
            summaries[task_type].append({
                "summary": summary[:300],
                "outcome": s.get("outcome"),
                "project": s.get("project")
            })
    return summaries


def extract_tool_patterns(sessions: List[Dict]) -> Dict[str, Any]:
    """Analyze tool usage patterns in successful vs problematic sessions."""
    successful_tools = {}
    problematic_tools = {}

    for s in sessions:
        tools = s.get("stats", {}).get("tools_used", [])
        has_issues = len(s.get("issues", [])) > 0
        successful_outcomes = ["completed", "completed_with_issues", "exploration_complete"]
        completed = s.get("outcome") in successful_outcomes

        target = problematic_tools if has_issues else (successful_tools if completed else None)
        if target is not None:
            for tool in tools:
                target[tool] = target.get(tool, 0) + 1

    return {
        "successful_sessions": successful_tools,
        "problematic_sessions": problematic_tools
    }


def extract_claude_code_feature_patterns(sessions: List[Dict]) -> Dict[str, Any]:
    """Analyze Claude Code feature usage patterns."""
    skills_usage = {}
    agents_usage = {}
    slash_commands_usage = {}

    sessions_with_skills = 0
    sessions_with_agents = 0
    sessions_with_slash_commands = 0

    # Track feature usage by outcome
    feature_outcomes = {
        "skills": {"completed": [], "had_issues": [], "other": []},
        "agents": {"completed": [], "had_issues": [], "other": []},
        "slash_commands": {"completed": [], "had_issues": [], "other": []}
    }

    for s in sessions:
        features = s.get("claude_code_features", {})
        outcome = s.get("outcome", "other")
        successful_outcomes = ["completed", "completed_with_issues", "exploration_complete"]
        problematic_outcomes = ["abandoned", "blocked"]
        if outcome in successful_outcomes:
            outcome_key = "completed"
        elif outcome in problematic_outcomes or len(s.get("issues", [])) > 0:
            outcome_key = "had_issues"
        else:
            outcome_key = "other"

        # Skills
        skills = features.get("skills_invoked", [])
        if skills:
            sessions_with_skills += 1
            for skill in skills:
                skill_name = skill if isinstance(skill, str) else skill.get("skill", "unknown")
                skills_usage[skill_name] = skills_usage.get(skill_name, 0) + 1
                feature_outcomes["skills"][outcome_key].append(skill_name)

        # Agents
        agents = features.get("agents_spawned", [])
        if agents:
            sessions_with_agents += 1
            for agent in agents:
                agent_type = agent if isinstance(agent, str) else agent.get("agent_type", "unknown")
                agents_usage[agent_type] = agents_usage.get(agent_type, 0) + 1
                feature_outcomes["agents"][outcome_key].append(agent_type)

        # Slash commands
        slash_cmds = features.get("slash_commands", [])
        if slash_cmds:
            sessions_with_slash_commands += 1
            for cmd in slash_cmds:
                cmd_name = cmd if isinstance(cmd, str) else cmd.get("command", "unknown")
                slash_commands_usage[cmd_name] = slash_commands_usage.get(cmd_name, 0) + 1
                feature_outcomes["slash_commands"][outcome_key].append(cmd_name)

    return {
        "skills_usage": dict(sorted(skills_usage.items(), key=lambda x: -x[1])),
        "agents_usage": dict(sorted(agents_usage.items(), key=lambda x: -x[1])),
        "slash_commands_usage": dict(sorted(slash_commands_usage.items(), key=lambda x: -x[1])),
        "sessions_with_skills": sessions_with_skills,
        "sessions_with_agents": sessions_with_agents,
        "sessions_with_slash_commands": sessions_with_slash_commands,
        "feature_outcomes": feature_outcomes
    }


def extract_outcome_distribution(sessions: List[Dict]) -> Dict[str, int]:
    """Extract the distribution of outcomes across sessions."""
    outcomes = {}
    for s in sessions:
        outcome = s.get("outcome", "unclear")
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
    return dict(sorted(outcomes.items(), key=lambda x: -x[1]))


def extract_confidence_distribution(sessions: List[Dict]) -> Dict[str, Any]:
    """Extract confidence score distribution."""
    scores = [s.get("completion_confidence") for s in sessions if s.get("completion_confidence") is not None]
    if not scores:
        return {"no_data": True}

    return {
        "total_with_scores": len(scores),
        "avg_confidence": round(sum(scores) / len(scores), 1),
        "high_confidence": sum(1 for s in scores if s >= 70),
        "medium_confidence": sum(1 for s in scores if 40 <= s < 70),
        "low_confidence": sum(1 for s in scores if s < 40),
        "by_assessment": {
            "high": [s for s in sessions if s.get("confidence_assessment") == "high"][:5],
            "low": [s for s in sessions if s.get("confidence_assessment") == "low"][:5]
        }
    }


def generate_qualitative_data(report: Dict) -> Dict:
    """Generate the qualitative analysis dataset."""
    sessions = report.get("sessions", [])

    # Filter valid sessions (has activity)
    valid_sessions = [
        s for s in sessions
        if s.get("stats", {}).get("user_messages", 0) > 0
    ]

    return {
        "metadata": {
            "report_period": f"{report.get('report_metadata', {}).get('start_date')} to {report.get('report_metadata', {}).get('end_date')}",
            "total_sessions": len(sessions),
            "valid_sessions": len(valid_sessions),
            "generated_at": datetime.now().isoformat()
        },
        "aggregate_stats": report.get("aggregate_statistics", {}),
        "outcome_distribution": extract_outcome_distribution(valid_sessions),
        "confidence_distribution": extract_confidence_distribution(valid_sessions),
        "sessions_with_issues": extract_sessions_with_issues(valid_sessions),
        "successful_sessions": extract_successful_sessions(valid_sessions),
        "abandoned_sessions": extract_abandoned_sessions(valid_sessions),
        "long_running_sessions": extract_long_running_sessions(valid_sessions),
        # Alias for backward compatibility
        "high_effort_sessions": extract_long_running_sessions(valid_sessions),
        "task_summaries_by_type": extract_task_summaries_by_type(valid_sessions),
        "tool_patterns": extract_tool_patterns(valid_sessions),
        "claude_code_features": {
            "aggregate": report.get("claude_code_features", {}),
            "patterns": extract_claude_code_feature_patterns(valid_sessions)
        },
        "detected_patterns": report.get("detected_patterns", {})
    }


def generate_analysis_prompt(data: Dict) -> str:
    """Generate a prompt for qualitative analysis."""

    issues_summary = json.dumps(data["sessions_with_issues"][:10], indent=2)
    successes_summary = json.dumps(data["successful_sessions"][:10], indent=2)
    long_running_summary = json.dumps(data.get("long_running_sessions", data.get("high_effort_sessions", []))[:5], indent=2)
    tool_patterns = json.dumps(data["tool_patterns"], indent=2)
    task_summaries = json.dumps(data["task_summaries_by_type"], indent=2)
    cc_features = json.dumps(data.get("claude_code_features", {}), indent=2)

    prompt = f"""# Claude Code Usage Qualitative Analysis

## Analysis Goal
Analyze the Claude Code session data to identify:
1. What patterns lead to successful outcomes
2. What patterns lead to issues or failures
3. Recommendations for improving prompting strategies
4. Lessons learned for future sessions

## Report Period
{data["metadata"]["report_period"]}
Total Sessions: {data["metadata"]["total_sessions"]} | Valid Sessions: {data["metadata"]["valid_sessions"]}

## Aggregate Statistics
- Completion Rate: {data["aggregate_stats"].get("completion_rate", "N/A")}%
- Issue Rate: {data["aggregate_stats"].get("issue_rate", "N/A")}%
- Total Duration: {data["aggregate_stats"].get("total_duration_hours", "N/A")} hours

---

## SESSIONS WITH ISSUES (for root cause analysis)

These sessions encountered problems. Analyze what went wrong and why.
Each session includes:
- `ai_summary`: Claude's auto-generated summary of the session (if available)
- `conversation_samples`: Initial prompts and response samples for context

```json
{issues_summary}
```

**Analysis Questions:**
- What types of tasks tend to have issues?
- Are there common tool combinations that lead to problems?
- What do the issue descriptions tell us about failure modes?
- What patterns in `ai_summary` indicate problematic sessions?
- How do the `conversation_samples.initial_prompts` contribute to issues?

---

## SUCCESSFUL SESSIONS (for pattern replication)

These sessions completed successfully. Identify what made them work.
Use `ai_summary` and `conversation_samples` to understand the context:

```json
{successes_summary}
```

**Analysis Questions:**
- What characteristics do successful sessions share?
- How do task summaries in successful sessions differ from problematic ones?
- What tool combinations are associated with success?
- What patterns in `conversation_samples.initial_prompts` correlate with success?
- Can you cite specific effective prompts from the samples?

---

## LONG-RUNNING SESSIONS (>60 min)

These sessions ran for extended periods (>60 minutes). Analyze efficiency.
Use `ai_summary` to understand the complexity and `conversation_samples` to see the prompting approach:

```json
{long_running_summary}
```

**Analysis Questions:**
- Were these sessions appropriately complex, or could they have been faster?
- What factors contributed to the extended duration?
- Did long duration correlate with better outcomes?
- What does the `ai_summary` reveal about why sessions took so long?
- Could different prompting (per `conversation_samples`) have improved efficiency?

---

## TOOL USAGE PATTERNS

Comparison of tools used in successful vs problematic sessions:

```json
{tool_patterns}
```

**Analysis Questions:**
- Which tools appear more often in problematic sessions?
- Are there tool combinations that predict success?

---

## TASK SUMMARIES BY TYPE

Sample of how tasks were described, grouped by type:

```json
{task_summaries}
```

**Analysis Questions:**
- Which task descriptions led to better outcomes?
- What makes a good vs poor task prompt?
- Are certain task types more prone to issues?

---

## CLAUDE CODE FEATURES USAGE

Usage of Claude Code features (skills, agents, slash commands):

```json
{cc_features}
```

**Analysis Questions:**
- Which skills are most commonly used? Are they effective?
- What agent types are spawned most frequently?
- Do sessions using certain features have higher completion rates?
- Which slash commands are popular? Any correlation with session outcomes?
- Are there feature combinations that correlate with success or issues?

---

## DELIVERABLES

Please provide:

### 1. Root Cause Analysis
Identify the top 3-5 root causes of session issues, with specific examples.
Use `ai_summary` fields to provide context for each root cause.

### 2. Success Patterns
Document 3-5 patterns that correlate with successful outcomes.
Include example prompts from `conversation_samples` that demonstrate good practices.

### 3. Prompting Best Practices
Based on task summaries and `conversation_samples.initial_prompts`, what makes an effective prompt for Claude Code?
Cite specific examples of good vs poor prompts from the data.

### 4. Tool Usage Recommendations
Which tool combinations should be encouraged or avoided?

### 5. Actionable Recommendations
Provide 5-10 specific, actionable recommendations for improving Claude Code usage.

### 6. Session Quality Metrics
Suggest metrics that could predict session success before or during execution.

### 7. Claude Code Feature Analysis
Analyze the usage of Claude Code features:
- Which skills are most valuable and should be used more?
- Which agent types are most effective for different task types?
- Are there underutilized features that could improve productivity?
- Recommendations for optimizing feature usage.
"""

    return prompt


def main():
    parser = argparse.ArgumentParser(
        description="Prepare data for qualitative analysis of Claude Code sessions"
    )
    parser.add_argument(
        "--input", "-i",
        type=str,
        required=True,
        help="Input report_data JSON file"
    )
    parser.add_argument(
        "--output-data", "-d",
        type=str,
        default="qualitative_data.json",
        help="Output file for extracted qualitative data"
    )
    parser.add_argument(
        "--output-prompt", "-p",
        type=str,
        default="analysis_prompt.md",
        help="Output file for the analysis prompt"
    )
    parser.add_argument(
        "--print-prompt",
        action="store_true",
        help="Print the prompt to stdout instead of saving"
    )

    args = parser.parse_args()

    # Load report
    print(f"Loading report from: {args.input}")
    report = load_report(args.input)

    # Generate qualitative data
    print("Extracting qualitative data...")
    qual_data = generate_qualitative_data(report)

    # Save qualitative data
    with open(args.output_data, 'w') as f:
        json.dump(qual_data, f, indent=2)
    print(f"Saved qualitative data to: {args.output_data}")

    # Generate analysis prompt
    print("Generating analysis prompt...")
    prompt = generate_analysis_prompt(qual_data)

    if args.print_prompt:
        print("\n" + "="*80 + "\n")
        print(prompt)
    else:
        with open(args.output_prompt, 'w') as f:
            f.write(prompt)
        print(f"Saved analysis prompt to: {args.output_prompt}")

    # Print summary
    print("\n--- Summary ---")
    print(f"Sessions with issues: {len(qual_data['sessions_with_issues'])}")
    print(f"Successful sessions: {len(qual_data['successful_sessions'])}")
    print(f"Abandoned sessions: {len(qual_data['abandoned_sessions'])}")
    print(f"Long-running sessions (>60 min): {len(qual_data['long_running_sessions'])}")
    print(f"Task types found: {list(qual_data['task_summaries_by_type'].keys())}")

    # Outcome distribution
    outcome_dist = qual_data.get("outcome_distribution", {})
    if outcome_dist:
        print("\n--- Outcome Distribution ---")
        for outcome, count in outcome_dist.items():
            print(f"  {outcome}: {count}")

    # Confidence distribution
    conf_dist = qual_data.get("confidence_distribution", {})
    if conf_dist and not conf_dist.get("no_data"):
        print("\n--- Confidence Distribution ---")
        print(f"  Avg confidence: {conf_dist.get('avg_confidence', 'N/A')}")
        print(f"  High confidence: {conf_dist.get('high_confidence', 0)}")
        print(f"  Medium confidence: {conf_dist.get('medium_confidence', 0)}")
        print(f"  Low confidence: {conf_dist.get('low_confidence', 0)}")

    # Claude Code features summary
    cc_patterns = qual_data.get("claude_code_features", {}).get("patterns", {})
    if cc_patterns:
        print(f"\nSessions using skills: {cc_patterns.get('sessions_with_skills', 0)}")
        print(f"Sessions using agents: {cc_patterns.get('sessions_with_agents', 0)}")
        print(f"Sessions using slash commands: {cc_patterns.get('sessions_with_slash_commands', 0)}")


if __name__ == "__main__":
    main()
