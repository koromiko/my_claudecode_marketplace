---
description: Conduct autonomous web research on a topic
argument-hint: <topic>
---

# Web Research

Launch the web-researcher agent to conduct autonomous research on a topic.

## Input

- **Topic**: `$1` (required) - Research topic or question

## Execution

Use the Task tool to spawn the `web-researcher` agent from this plugin.

Pass these values to the agent in the prompt:
- Research topic: `$1`
- Plugin root path: `${CLAUDE_PLUGIN_ROOT}`

The agent will autonomously:
1. Search the web for relevant sources
2. Map promising sites for deeper content
3. Scrape and analyze key pages
4. Extract structured data when applicable
5. Compile findings into a comprehensive report

## Output

The agent will return a research report including:
- Executive summary
- Key findings organized by subtopic
- Source citations with URLs
- Recommendations for further research
