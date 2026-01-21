# Firecrawl MCP Tool Reference

Complete parameter reference for all Firecrawl MCP tools.

## firecrawl_scrape

Scrapes a single URL and returns content in specified formats.

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | string | Yes | - | URL to scrape |
| `formats` | array | No | ["markdown"] | Output formats: "markdown", "html", "links", "screenshot", "rawHtml" |
| `onlyMainContent` | boolean | No | true | Extract only main content, excluding nav/footer |
| `includeTags` | array | No | - | Only include these HTML tags |
| `excludeTags` | array | No | - | Exclude these HTML tags |
| `waitFor` | number | No | - | Wait milliseconds before extraction |
| `timeout` | number | No | 30000 | Request timeout in milliseconds |
| `mobile` | boolean | No | false | Use mobile viewport |

**Example:**
```json
{
  "url": "https://example.com/page",
  "formats": ["markdown", "screenshot"],
  "onlyMainContent": true,
  "waitFor": 2000
}
```

---

## firecrawl_batch_scrape

Scrapes multiple URLs efficiently with built-in rate limiting.

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `urls` | array | Yes | - | Array of URLs to scrape |
| `formats` | array | No | ["markdown"] | Output formats for all URLs |
| `onlyMainContent` | boolean | No | true | Extract only main content |

**Returns:** Job ID for status checking with `firecrawl_check_batch_status`

**Example:**
```json
{
  "urls": [
    "https://example.com/page1",
    "https://example.com/page2",
    "https://example.com/page3"
  ],
  "formats": ["markdown"]
}
```

---

## firecrawl_check_batch_status

Checks the status of a batch scrape job.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string | Yes | Batch job ID from firecrawl_batch_scrape |

**Returns:** Status and results when complete

---

## firecrawl_crawl

Initiates an asynchronous crawl of a website starting from a URL.

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | string | Yes | - | Starting URL for crawl |
| `limit` | number | No | 10 | Maximum pages to crawl |
| `maxDepth` | number | No | - | Maximum link depth from start URL |
| `allowedDomains` | array | No | - | Only crawl these domains |
| `excludePaths` | array | No | - | URL paths to skip (regex supported) |
| `includePaths` | array | No | - | Only crawl these paths (regex supported) |

**Returns:** Crawl ID for status checking

**Example:**
```json
{
  "url": "https://docs.example.com",
  "limit": 50,
  "maxDepth": 3,
  "includePaths": ["/api/", "/guides/"]
}
```

---

## firecrawl_check_crawl_status

Checks the status and retrieves results of a crawl job.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string | Yes | Crawl ID from firecrawl_crawl |

**Returns:**
- `status`: "scraping", "completed", "failed"
- `completed`: Number of pages completed
- `total`: Total pages found
- `data`: Array of scraped page content (when complete)

---

## firecrawl_map

Discovers and maps all URLs on a website.

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | string | Yes | - | Website URL to map |
| `search` | string | No | - | Filter results containing this text |
| `limit` | number | No | 100 | Maximum URLs to return |
| `ignoreSitemap` | boolean | No | false | Skip sitemap, crawl directly |

**Returns:** Array of discovered URLs

**Example:**
```json
{
  "url": "https://example.com",
  "search": "blog",
  "limit": 50
}
```

---

## firecrawl_search

Performs web search and extracts content from results.

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | Yes | - | Search query |
| `limit` | number | No | 5 | Number of results to return |
| `lang` | string | No | "en" | Language code |
| `country` | string | No | "us" | Country code |
| `scrapeOptions` | object | No | - | Options for content extraction |

**Example:**
```json
{
  "query": "React hooks best practices 2024",
  "limit": 10,
  "scrapeOptions": {
    "formats": ["markdown"],
    "onlyMainContent": true
  }
}
```

---

## firecrawl_extract

Extracts structured data from URLs using a schema.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `urls` | array | Yes | URLs to extract data from |
| `prompt` | string | No | Natural language extraction instructions |
| `schema` | object | No | JSON Schema for structured output |
| `systemPrompt` | string | No | Custom system prompt for extraction |
| `allowExternalLinks` | boolean | No | Follow links to other domains |

**Note:** Provide either `prompt` OR `schema`, not both.

**Example with prompt:**
```json
{
  "urls": ["https://example.com/product"],
  "prompt": "Extract the product name, price, and key features"
}
```

**Example with schema:**
```json
{
  "urls": ["https://example.com/product"],
  "schema": {
    "type": "object",
    "properties": {
      "productName": {"type": "string"},
      "price": {"type": "number"},
      "features": {
        "type": "array",
        "items": {"type": "string"}
      }
    },
    "required": ["productName", "price"]
  }
}
```

See `schema-examples.md` for more schema patterns.
