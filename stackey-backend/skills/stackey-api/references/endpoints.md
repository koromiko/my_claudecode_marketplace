# Stackey API - Endpoint Reference

Complete documentation for all StackeyBackend API endpoints.

## Blocks

### GET /blocks - List blocks

List all blocks with optional filtering. Non-admins only see public blocks.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `tags` | string | Comma-separated tags to filter by (uses overlap) |
| `search` | string | Search in title and description |
| `limit` | number | Items per page (default: 20, max: 100) |
| `after` | string | Cursor for next page (created_at timestamp) |
| `before` | string | Cursor for previous page (created_at timestamp) |

**Example:**
```bash
# List all public blocks
curl "http://127.0.0.1:54321/functions/v1/blocks"

# Filter by tags
curl "http://127.0.0.1:54321/functions/v1/blocks?tags=camera,zoom"

# Search with pagination
curl "http://127.0.0.1:54321/functions/v1/blocks?search=pan&limit=10"

# Get next page using cursor
curl "http://127.0.0.1:54321/functions/v1/blocks?limit=10&after=2026-01-15T09:00:00Z"
```

**Response:**
```json
{
  "data": [
    {
      "id": "uuid",
      "title": "Zoom In",
      "description": "Smooth zoom effect",
      "subtitle": "Dynamic camera movement",
      "prompt_text": "Smooth zoom in on the subject",
      "gradient_id": 1,
      "icon": "zoom-in",
      "tags": ["camera", "zoom"],
      "is_public": true,
      "created_by": "user-uuid",
      "created_at": "2026-01-15T10:00:00Z",
      "updated_at": "2026-01-15T10:00:00Z",
      "block_media": [
        {
          "id": "media-uuid",
          "type": "video",
          "url": "https://...",
          "filename": "zoom-example.mp4",
          "sort_order": 0
        }
      ]
    }
  ],
  "pageInfo": {
    "hasNextPage": true,
    "hasPreviousPage": false,
    "startCursor": "2026-01-15T10:00:00Z",
    "endCursor": "2026-01-15T09:00:00Z",
    "totalCount": 150
  }
}
```

### GET /blocks/:id - Get single block

Retrieve a specific block by ID with its media attachments.

**Example:**
```bash
curl "http://127.0.0.1:54321/functions/v1/blocks/abc123-uuid"
```

**Response:** Single block object (same structure as list item)

**Errors:**
- `404` - Block not found (also returned for private blocks when not admin)

### POST /blocks - Create block (Admin)

Create a new block. Requires admin authentication.

**Request Body:**
```json
{
  "title": "Pan Left",           // required
  "description": "Smooth pan",   // optional
  "subtitle": "Camera movement", // optional
  "prompt_text": "Smooth pan left", // optional
  "gradient_id": 1,              // optional, default 1
  "icon": "pan-left",            // optional
  "tags": ["camera", "pan"],     // optional, default []
  "is_public": false             // optional, default false
}
```

**Example:**
```bash
curl -X POST \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "Pan Left", "tags": ["camera", "pan"], "is_public": true}' \
  "http://127.0.0.1:54321/functions/v1/blocks"
```

**Response:** Created block object (201)

### PATCH /blocks/:id - Update block (Admin)

Update an existing block. Only provided fields are updated.

**Request Body:**
```json
{
  "title": "New Title",        // optional
  "description": "New desc",   // optional
  "subtitle": "New subtitle",  // optional
  "prompt_text": "New prompt", // optional
  "gradient_id": 2,            // optional
  "icon": "new-icon",          // optional
  "tags": ["new", "tags"],     // optional
  "is_public": true            // optional
}
```

**Example:**
```bash
curl -X PATCH \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"is_public": true}' \
  "http://127.0.0.1:54321/functions/v1/blocks/abc123-uuid"
```

**Response:** Updated block object with media

### DELETE /blocks/:id - Delete block (Admin)

Delete a block and all its associated media (both records and storage files).

**Example:**
```bash
curl -X DELETE \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  "http://127.0.0.1:54321/functions/v1/blocks/abc123-uuid"
```

**Response:**
```json
{ "success": true }
```

---

## Users

### GET /users/me - Get profile

Get the authenticated user's profile.

**Example:**
```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:54321/functions/v1/users/me"
```

**Response:**
```json
{
  "id": "user-uuid",
  "email": "user@example.com",
  "display_name": "John Doe",
  "avatar_url": "https://...",
  "role": "user",
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-01-15T10:00:00Z"
}
```

### PATCH /users/me - Update profile

Update the authenticated user's profile.

**Request Body:**
```json
{
  "display_name": "New Name",  // optional
  "avatar_url": "https://..."  // optional
}
```

**Example:**
```bash
curl -X PATCH \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"display_name": "New Name"}' \
  "http://127.0.0.1:54321/functions/v1/users/me"
```

**Response:** Updated user object

---

## Favorites

### GET /favorites - List favorites

Get all blocks favorited by the authenticated user with cursor-based pagination.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | number | Items per page (default: 20, max: 100) |
| `after` | string | Cursor for next page (created_at timestamp) |
| `before` | string | Cursor for previous page (created_at timestamp) |

**Example:**
```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:54321/functions/v1/favorites"

# Get next page using cursor
curl -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:54321/functions/v1/favorites?limit=10&after=2026-01-15T09:00:00Z"
```

**Response:**
```json
{
  "data": [
    {
      "id": "block-uuid",
      "title": "Zoom In",
      "description": "...",
      "subtitle": "Dynamic camera movement",
      "prompt_text": "Smooth zoom in",
      "gradient_id": 1,
      "icon": "zoom-in",
      "tags": ["camera"],
      "is_public": true,
      "favorited_at": "2026-01-15T10:00:00Z",
      "block_media": [...]
    }
  ],
  "pageInfo": {
    "hasNextPage": true,
    "hasPreviousPage": false,
    "startCursor": "2026-01-15T10:00:00Z",
    "endCursor": "2026-01-15T09:00:00Z",
    "totalCount": 25
  }
}
```

### POST /favorites - Add favorite

Add a block to the user's favorites.

**Request Body:**
```json
{
  "block_id": "uuid-of-block"  // required
}
```

**Example:**
```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"block_id": "abc123-uuid"}' \
  "http://127.0.0.1:54321/functions/v1/favorites"
```

**Response:**
```json
{
  "user_id": "user-uuid",
  "block_id": "block-uuid",
  "created_at": "2026-01-15T10:00:00Z"
}
```

**Errors:**
- `404` - Block not found
- `409` - Block already favorited

### DELETE /favorites/:blockId - Remove favorite

Remove a block from the user's favorites.

**Example:**
```bash
curl -X DELETE \
  -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:54321/functions/v1/favorites/abc123-uuid"
```

**Response:**
```json
{ "success": true }
```

---

## Block Media (Admin)

### POST /block-media - Upload media

Upload an image or video to a block. Uses multipart form data.

**Form Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `file` | File | Image or video file (required) |
| `block_id` | string | Target block UUID (required) |
| `sort_order` | number | Display order (optional, default 0) |

**Example:**
```bash
curl -X POST \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -F "file=@example.mp4" \
  -F "block_id=abc123-uuid" \
  -F "sort_order=0" \
  "http://127.0.0.1:54321/functions/v1/block-media"
```

**Response:**
```json
{
  "id": "media-uuid",
  "block_id": "block-uuid",
  "type": "video",
  "url": "https://...supabase.co/storage/v1/object/public/block-media/...",
  "filename": "example.mp4",
  "mime_type": "video/mp4",
  "size_bytes": 1048576,
  "sort_order": 0,
  "created_at": "2026-01-15T10:00:00Z"
}
```

**Errors:**
- `400` - File is required / block_id is required / File must be an image or video
- `404` - Block not found

### DELETE /block-media/:id - Delete media

Delete a media file from storage and database.

**Example:**
```bash
curl -X DELETE \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  "http://127.0.0.1:54321/functions/v1/block-media/media-uuid"
```

**Response:**
```json
{ "success": true }
```

---

## Error Responses

All error responses follow this format:

```json
{
  "error": "Error message describing what went wrong"
}
```

**HTTP Status Codes:**
| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 400 | Bad request (validation error) |
| 401 | Unauthorized (no/invalid token) |
| 403 | Forbidden (not admin) |
| 404 | Not found |
| 405 | Method not allowed |
| 409 | Conflict (e.g., duplicate favorite) |
| 500 | Server error |
