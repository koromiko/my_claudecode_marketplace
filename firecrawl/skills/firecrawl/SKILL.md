---
name: firecrawl
description: Use this skill when users mention "scrape a URL", "web scraping", "crawl website", "extract data from webpage", "take screenshot of page", "firecrawl", "get webpage content", "batch scrape", "web search with content", or need to extract structured data from websites.
version: 1.0.0
context: fork
---

# Firecrawl Web Data Extraction

Firecrawl transforms websites into AI-ready formats, handling JavaScript rendering, anti-bot systems, and dynamic content automatically.

## Available MCP Tools

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `mcp__firecrawl__firecrawl_scrape` | Single page extraction | Quick content from one URL |
| `mcp__firecrawl__firecrawl_batch_scrape` | Multiple URLs with rate limiting | Scraping 2+ known URLs |
| `mcp__firecrawl__firecrawl_crawl` | Async multi-page crawling | Full site/section extraction |
| `mcp__firecrawl__firecrawl_check_crawl_status` | Monitor crawl progress | After starting a crawl |
| `mcp__firecrawl__firecrawl_map` | Discover URLs on a site | Before crawling to find pages |
| `mcp__firecrawl__firecrawl_search` | Web search + content extraction | Finding info across the web |
| `mcp__firecrawl__firecrawl_extract` | Structured data with schemas | Extracting specific fields |
| `mcp__firecrawl__firecrawl_check_batch_status` | Monitor batch progress | After starting batch scrape |

## Tool Selection Guide

### Quick Single Page Content
```
Use: firecrawl_scrape
Formats: markdown (default), html, links, screenshot
```

### Multiple Known URLs
```
Use: firecrawl_batch_scrape
- More efficient than individual scrapes
- Built-in rate limiting
- Returns job ID for status checking
```

### Discover Site Structure
```
Use: firecrawl_map
- Returns list of URLs on a domain
- Use search parameter to filter (e.g., "blog", "docs")
- Run this BEFORE crawl to understand scope
```

### Full Site/Section Crawl
```
1. First: firecrawl_map to discover URLs
2. Then: firecrawl_crawl with appropriate limit
3. Monitor: firecrawl_check_crawl_status
```

### Web Search with Content
```
Use: firecrawl_search
- Searches the web and extracts content from results
- Good for finding information across multiple sites
```

### Extract Structured Data
```
Use: firecrawl_extract
- Define a schema for consistent output
- Best for: product info, contact details, pricing
- See references/schema-examples.md for patterns
```

## Common Patterns

### Basic Page Scrape
```
Tool: firecrawl_scrape
Params:
  url: "https://example.com/page"
  formats: ["markdown"]
```

### Screenshot Capture
```
Tool: firecrawl_scrape
Params:
  url: "https://example.com"
  formats: ["screenshot"]
```

### Map Site Then Crawl
```
1. firecrawl_map
   url: "https://docs.example.com"
   search: "api"  # optional filter

2. Review returned URLs, then:

3. firecrawl_crawl
   url: "https://docs.example.com/api"
   limit: 50
```

### Extract with Schema
```
Tool: firecrawl_extract
Params:
  urls: ["https://example.com/product"]
  prompt: "Extract product information"
  schema: {
    "type": "object",
    "properties": {
      "name": {"type": "string"},
      "price": {"type": "number"},
      "description": {"type": "string"}
    }
  }
```

## Best Practices

1. **Start with map**: Before crawling, use `firecrawl_map` to understand site structure
2. **Set reasonable limits**: Default crawl limit is 10; increase only when needed
3. **Use specific URLs**: Target specific sections rather than entire sites
4. **Prefer markdown**: Most efficient format for AI processing
5. **Batch when possible**: Use batch_scrape for multiple known URLs
6. **Monitor async jobs**: Use status check tools for crawl and batch operations

## Error Handling

- **Rate limits**: Built-in handling, but large operations may queue
- **Blocked content**: Some sites may block scraping; try different approaches
- **Timeouts**: Large crawls are async; always check status

## Plugin Commands

| Command | Description |
|---------|-------------|
| `/firecrawl:scrape <url>` | Quick single-page scrape |
| `/firecrawl:crawl <url> [limit]` | Start website crawl |
| `/firecrawl:map <url> [search]` | Discover site URLs |
| `/firecrawl:search <query>` | Web search with content |
| `/firecrawl:extract <url> <schema-or-prompt>` | Extract structured data |
| `/firecrawl:research <topic>` | Autonomous web research |

## Additional Resources

- `references/tool-reference.md` - Complete tool parameters
- `references/schema-examples.md` - JSON schema patterns for extraction
- `references/action-sequences.md` - Dynamic content handling
