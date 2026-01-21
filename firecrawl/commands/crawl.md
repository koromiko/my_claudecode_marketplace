---
description: Start an asynchronous crawl of a website
argument-hint: <url> [limit]
---

# Crawl Website

Start an asynchronous crawl of a website and monitor its progress.

## Input

- **URL**: `$1` (required) - Starting URL for the crawl
- **Limit**: `$2` (optional) - Maximum pages to crawl (default: 10)

## Execution

1. First, use `mcp__firecrawl__firecrawl_map` to preview the site structure:
   - `url`: The provided URL
   - `limit`: 20

2. Report the discovered URLs to the user and confirm before proceeding.

3. Start the crawl with `mcp__firecrawl__firecrawl_crawl`:
   - `url`: The provided URL
   - `limit`: The provided limit or 10

4. Report the crawl ID to the user.

5. Check status with `mcp__firecrawl__firecrawl_check_crawl_status`:
   - `id`: The crawl ID

6. If status is "scraping", inform the user of progress and offer to check again.

7. When complete, present the results organized by page.

## Output

Provide a summary of:
- Total pages crawled
- Key content discovered
- Any errors encountered

For large crawls, summarize the content and offer to dive deeper into specific pages.
