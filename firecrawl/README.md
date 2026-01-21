# Firecrawl Plugin for Claude Code

Web scraping, crawling, and data extraction using Firecrawl API and the official MCP server.

## Overview

This plugin integrates [Firecrawl](https://firecrawl.dev) with Claude Code, providing powerful web data extraction capabilities:

- **JavaScript rendering**: Handles dynamic content, SPAs, and client-side rendered pages
- **Anti-bot handling**: Automatic proxy rotation and rate limiting
- **Multiple output formats**: Markdown, HTML, screenshots, structured JSON
- **Intelligent extraction**: Schema-based structured data extraction

## Requirements

- Local Firecrawl instance running at `http://localhost:3002`
- Node.js (for `npx` to run the MCP server)

## Setup

1. Start your local Firecrawl container:
   ```bash
   docker run -d -p 3002:3002 firecrawl/firecrawl
   ```

2. Add this plugin to your Claude Code plugins directory

3. The MCP server will connect automatically when the plugin loads

## Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/firecrawl:scrape <url>` | Scrape a single page | `/firecrawl:scrape https://example.com` |
| `/firecrawl:crawl <url> [limit]` | Crawl a website | `/firecrawl:crawl https://docs.example.com 50` |
| `/firecrawl:map <url> [search]` | Discover site URLs | `/firecrawl:map https://example.com blog` |
| `/firecrawl:search <query>` | Web search with content | `/firecrawl:search "React best practices"` |
| `/firecrawl:extract <url> <prompt>` | Extract structured data | `/firecrawl:extract https://store.com/product "Extract price and features"` |
| `/firecrawl:research <topic>` | Autonomous web research | `/firecrawl:research "GraphQL vs REST APIs"` |

## MCP Tools

The plugin exposes these Firecrawl tools via MCP:

- `firecrawl_scrape` - Single page extraction
- `firecrawl_batch_scrape` - Multiple URLs with rate limiting
- `firecrawl_check_batch_status` - Monitor batch progress
- `firecrawl_map` - Discover URLs on a website
- `firecrawl_search` - Web search with content extraction
- `firecrawl_crawl` - Async multi-page crawling
- `firecrawl_check_crawl_status` - Track crawl progress
- `firecrawl_extract` - Structured data extraction with schemas

## Skill Triggers

The `firecrawl` skill activates when you mention:
- "scrape a URL"
- "web scraping"
- "crawl website"
- "extract data from webpage"
- "take screenshot of page"
- "firecrawl"
- "get webpage content"

## Examples

### Scrape a documentation page

```
/firecrawl:scrape https://docs.example.com/getting-started
```

### Discover all URLs on a site

```
/firecrawl:map https://example.com
```

### Search and extract information

```
/firecrawl:search "best practices for API design 2024"
```

### Extract product information

```
/firecrawl:extract https://store.com/product {"type":"object","properties":{"name":{"type":"string"},"price":{"type":"number"}}}
```

### Conduct comprehensive research

```
/firecrawl:research "current state of WebAssembly adoption"
```

## Directory Structure

```
firecrawl/
├── .claude-plugin/
│   └── plugin.json          # Plugin manifest
├── .mcp.json                 # MCP server configuration
├── skills/
│   └── firecrawl/
│       ├── SKILL.md          # Main skill with usage patterns
│       └── references/
│           ├── tool-reference.md      # Complete tool parameters
│           ├── schema-examples.md     # JSON schema patterns
│           └── action-sequences.md    # Dynamic content handling
├── commands/
│   ├── scrape.md             # /firecrawl:scrape
│   ├── crawl.md              # /firecrawl:crawl
│   ├── map.md                # /firecrawl:map
│   ├── search.md             # /firecrawl:search
│   ├── extract.md            # /firecrawl:extract
│   └── research.md           # /firecrawl:research
├── agents/
│   └── web-researcher-agent.md
└── README.md
```

## Configuration

The plugin uses a local Firecrawl instance by default. To modify the API URL, edit `.mcp.json`:

```json
{
  "mcpServers": {
    "firecrawl": {
      "command": "npx",
      "args": ["-y", "firecrawl-mcp"],
      "env": {
        "FIRECRAWL_API_URL": "http://localhost:3002"
      }
    }
  }
}
```

For cloud Firecrawl with API key:

```json
{
  "mcpServers": {
    "firecrawl": {
      "command": "npx",
      "args": ["-y", "firecrawl-mcp"],
      "env": {
        "FIRECRAWL_API_KEY": "your-api-key"
      }
    }
  }
}
```

## References

- [Firecrawl Documentation](https://docs.firecrawl.dev)
- [Firecrawl MCP Server](https://github.com/mendableai/firecrawl-mcp-server)
- [MCP Protocol](https://modelcontextprotocol.io)
