# Action Sequences for Dynamic Content

Patterns for handling JavaScript-rendered content, single-page applications, and dynamic pages.

## Wait Strategies

### Basic Wait for Content

Use `waitFor` parameter when content loads after page render:

```json
{
  "url": "https://example.com/dynamic-page",
  "formats": ["markdown"],
  "waitFor": 3000
}
```

**When to use:**
- Pages with client-side rendering (React, Vue, Angular)
- Content loaded via API calls after page load
- Lazy-loaded sections

### Recommended Wait Times

| Content Type | Wait Time | Notes |
|-------------|-----------|-------|
| Static HTML | 0 (default) | No wait needed |
| Light JavaScript | 1000-2000ms | Basic hydration |
| SPA with API calls | 2000-3000ms | API response time |
| Heavy dynamic content | 3000-5000ms | Multiple async loads |
| Infinite scroll | Use actions | Scroll-triggered content |

---

## Common Sequences

### Documentation Site

1. **Map the site first** to understand structure:
```
firecrawl_map
  url: "https://docs.example.com"
  search: "api"  # filter for API docs
```

2. **Review URLs**, then batch scrape relevant pages:
```
firecrawl_batch_scrape
  urls: [selected URLs from map]
  formats: ["markdown"]
```

### E-commerce Product Pages

1. **Single product** with wait for dynamic pricing:
```
firecrawl_scrape
  url: "https://store.com/product/123"
  formats: ["markdown"]
  waitFor: 2000
  onlyMainContent: true
```

2. **Multiple products** efficiently:
```
firecrawl_batch_scrape
  urls: [array of product URLs]
  formats: ["markdown"]
```

### News/Blog Site

1. **Map to find articles**:
```
firecrawl_map
  url: "https://news.example.com"
  search: "2024"  # recent articles
  limit: 100
```

2. **Crawl specific section**:
```
firecrawl_crawl
  url: "https://news.example.com/tech"
  limit: 25
  maxDepth: 2
```

### Research Workflow

1. **Search for topic**:
```
firecrawl_search
  query: "machine learning best practices 2024"
  limit: 10
```

2. **Deep dive on best results**:
```
firecrawl_scrape
  url: [selected URL from search]
  formats: ["markdown"]
```

3. **Extract structured data**:
```
firecrawl_extract
  urls: [key URLs]
  prompt: "Extract key techniques, tools, and recommendations"
```

---

## Handling SPA Content

### React/Next.js Sites

Most React apps need wait time for hydration:

```json
{
  "url": "https://react-app.example.com",
  "waitFor": 2000,
  "formats": ["markdown"],
  "onlyMainContent": true
}
```

### Vue/Nuxt Sites

Similar approach:

```json
{
  "url": "https://vue-app.example.com",
  "waitFor": 2000,
  "formats": ["markdown"]
}
```

### Angular Sites

Angular apps often need longer waits:

```json
{
  "url": "https://angular-app.example.com",
  "waitFor": 3000,
  "formats": ["markdown"]
}
```

---

## Mobile Content

Some sites serve different content to mobile devices:

```json
{
  "url": "https://example.com",
  "mobile": true,
  "formats": ["markdown", "screenshot"]
}
```

**Use mobile mode for:**
- Mobile-specific content
- Responsive design testing
- Sites that redirect mobile users

---

## Screenshot Strategies

### Full Page Screenshot

```json
{
  "url": "https://example.com",
  "formats": ["screenshot"],
  "waitFor": 2000
}
```

### Combined with Content

```json
{
  "url": "https://example.com",
  "formats": ["markdown", "screenshot"]
}
```

**Screenshot use cases:**
- Visual verification
- Design/layout capture
- Content that doesn't convert well to markdown
- Charts, graphs, diagrams

---

## Async Operations

### Crawl with Status Checking

1. **Start crawl**:
```
firecrawl_crawl
  url: "https://docs.example.com"
  limit: 100
→ Returns: { "id": "crawl-abc123" }
```

2. **Check status periodically**:
```
firecrawl_check_crawl_status
  id: "crawl-abc123"
→ Returns: { "status": "scraping", "completed": 45, "total": 100 }
```

3. **Final check for results**:
```
firecrawl_check_crawl_status
  id: "crawl-abc123"
→ Returns: { "status": "completed", "data": [...] }
```

### Batch with Status Checking

1. **Start batch**:
```
firecrawl_batch_scrape
  urls: [50 URLs]
→ Returns: { "id": "batch-xyz789" }
```

2. **Check status**:
```
firecrawl_check_batch_status
  id: "batch-xyz789"
```

---

## Error Recovery

### Timeout Handling

If a scrape times out, try:
1. Increase timeout value
2. Add waitFor delay
3. Use onlyMainContent: true to reduce processing

### Rate Limit Response

The MCP server handles rate limiting automatically. For large operations:
1. Use batch operations instead of individual calls
2. Set reasonable limits on crawls
3. Monitor async job status

### Content Not Found

If expected content is missing:
1. Check if the page requires JavaScript (add waitFor)
2. Try mobile: true for mobile-only content
3. Verify URL is correct and accessible
4. Check if content is behind authentication
