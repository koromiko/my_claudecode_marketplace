---
description: Search the web and extract content from results
argument-hint: <query>
---

# Web Search

Search the web and extract content from the top results.

## Input

- **Query**: `$1` (required) - Search query

## Execution

Call `mcp__firecrawl__firecrawl_search` with:
- `query`: The provided query
- `limit`: 5
- `scrapeOptions`:
  - `formats`: ["markdown"]
  - `onlyMainContent`: true

## Output

Present results organized by source:
1. Source title and URL
2. Key information relevant to the query
3. Notable quotes or data points

After presenting results, offer to:
- Deep dive into a specific source
- Search with refined query
- Extract structured data from specific URLs
