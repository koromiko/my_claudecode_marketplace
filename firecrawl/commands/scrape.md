---
description: Scrape content from a single URL
argument-hint: <url>
---

# Scrape URL

Use the `mcp__firecrawl__firecrawl_scrape` tool to extract content from the provided URL.

## Input

- **URL**: `$1` (required)

## Execution

Call `mcp__firecrawl__firecrawl_scrape` with:
- `url`: The provided URL
- `formats`: ["markdown"]
- `onlyMainContent`: true

## Output

Present the scraped content in a clean, readable format. If the content is very long, summarize the key sections and offer to provide more detail on specific parts.

If the scrape fails, suggest:
1. Check if the URL is correct and accessible
2. Try adding a wait time for dynamic content
3. Verify the site allows scraping
