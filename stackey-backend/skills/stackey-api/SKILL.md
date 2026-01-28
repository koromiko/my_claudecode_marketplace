---
name: stackey-api
description: Use this skill when users mention "Stackey API", "blocks endpoint", "favorites endpoint", "block-media", "Stackey backend", or when working on code that calls the StackeyBackend Supabase Edge Functions.
version: 1.0.0
context: fork
---

# Stackey Backend API

REST API reference for the StackeyBackend Supabase Edge Functions. All endpoints are served from Supabase Edge Functions.

## Base URL

- **Local**: `http://127.0.0.1:54321/functions/v1`
- **Production**: `https://<project-ref>.supabase.co/functions/v1`

## Authentication Levels

| Level | Description | Header Required |
|-------|-------------|-----------------|
| Public | No authentication | None |
| User | Valid JWT token | `Authorization: Bearer <token>` |
| Admin | JWT + `role='admin'` | `Authorization: Bearer <token>` |

## Endpoints Overview

| Endpoint | Methods | Auth | Purpose |
|----------|---------|------|---------|
| `/blocks` | GET | Public | List blocks with filtering |
| `/blocks` | POST | Admin | Create a block |
| `/blocks/:id` | GET | Public | Get single block |
| `/blocks/:id` | PATCH | Admin | Update a block |
| `/blocks/:id` | DELETE | Admin | Delete a block |
| `/users/me` | GET, PATCH | User | User profile |
| `/favorites` | GET, POST | User | List/add favorites |
| `/favorites/:blockId` | DELETE | User | Remove favorite |
| `/block-media` | POST | Admin | Upload media |
| `/block-media/:id` | DELETE | Admin | Delete media |

## Quick Examples

### List public blocks

```bash
curl "http://127.0.0.1:54321/functions/v1/blocks"
```

### Get user profile (requires auth)

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:54321/functions/v1/users/me"
```

### Create a block (admin only)

```bash
curl -X POST \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "Zoom In", "tags": ["camera", "zoom"], "is_public": true}' \
  "http://127.0.0.1:54321/functions/v1/blocks"
```

## Response Format

All endpoints return JSON with consistent structure:

**Success:**
```json
{
  "blocks": [...],
  "total": 50
}
```

**Error:**
```json
{
  "error": "Error message"
}
```

## Common Headers

All requests should include:
- `Content-Type: application/json` (for POST/PATCH)
- `Authorization: Bearer <token>` (for authenticated endpoints)

## Additional Resources

For detailed endpoint documentation with all parameters and response schemas, see `references/endpoints.md`.
