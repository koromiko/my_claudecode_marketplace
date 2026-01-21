---
description: Discover and list all URLs on a website
argument-hint: <url> [search]
---

# Map Website URLs

Discover all URLs on a website, optionally filtered by search term.

## Input

- **URL**: `$1` (required) - Website URL to map
- **Search**: `$2` (optional) - Filter results containing this text

## Execution

Call `mcp__firecrawl__firecrawl_map` with:
- `url`: The provided URL
- `search`: The search filter if provided
- `limit`: 100

## Output

Present the discovered URLs in an organized format:
1. Group by URL pattern/section if applicable
2. Show total count
3. Highlight any notable sections (docs, blog, api, etc.)

Suggest next steps:
- Use `/firecrawl:crawl` to scrape multiple pages
- Use `/firecrawl:scrape` for specific URLs
- Refine with a search filter if too many results
