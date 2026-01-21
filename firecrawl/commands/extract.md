---
description: Extract structured data from a URL using a schema or prompt
argument-hint: <url> <schema-or-prompt>
---

# Extract Structured Data

Extract structured data from a URL using either a natural language prompt or JSON schema.

## Input

- **URL**: `$1` (required) - URL to extract data from
- **Schema or Prompt**: `$2` (required) - Either:
  - A natural language prompt describing what to extract
  - A JSON schema defining the structure

## Execution

Determine if `$2` is a JSON schema (starts with `{`) or a natural language prompt.

### If Natural Language Prompt

Call `mcp__firecrawl__firecrawl_extract` with:
- `urls`: [`$1`]
- `prompt`: `$2`

### If JSON Schema

Call `mcp__firecrawl__firecrawl_extract` with:
- `urls`: [`$1`]
- `schema`: The parsed JSON schema

## Output

Present the extracted data in a clean, structured format:
1. Format as a table if applicable
2. Use JSON for complex nested structures
3. Highlight any fields that couldn't be extracted

For schema examples, refer to `skills/firecrawl/references/schema-examples.md`.
