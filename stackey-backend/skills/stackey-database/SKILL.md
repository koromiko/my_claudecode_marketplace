---
name: stackey-database
description: Use this skill when users mention "Stackey database", "blocks table", "users table", "favorites table", "block_media table", "Stackey schema", "RLS policies", or when working on database migrations or queries for StackeyBackend.
version: 1.0.0
context: fork
---

# Stackey Database Schema

PostgreSQL database schema for the StackeyBackend Supabase project.

## Tables Overview

| Table | Purpose | Key Relationships |
|-------|---------|-------------------|
| `users` | User profiles | Extends `auth.users` |
| `blocks` | Video generation presets | Has many `block_media` |
| `block_media` | Images/videos for blocks | Belongs to `blocks` |
| `favorites` | User-block favorites | Many-to-many junction |

## Entity Relationship

```
auth.users (Supabase)
    │
    ▼
  users ──────────────────┐
    │                     │
    │                     │
    ▼                     ▼
 blocks ◀──────────── favorites
    │
    ▼
block_media
```

## Quick Reference

### Users Table

```sql
-- Columns: id, email, display_name, avatar_url, role, created_at, updated_at
-- role: 'user' | 'admin'

SELECT * FROM users WHERE id = 'user-uuid';
```

### Blocks Table

```sql
-- Columns: id, title, description, tags, is_public, created_by, created_at, updated_at
-- tags: text[] with GIN index

SELECT * FROM blocks WHERE 'camera' = ANY(tags);
SELECT * FROM blocks WHERE is_public = true;
```

### Block Media Table

```sql
-- Columns: id, block_id, type, url, filename, mime_type, size_bytes, sort_order, created_at
-- type: 'image' | 'video'

SELECT * FROM block_media WHERE block_id = 'block-uuid' ORDER BY sort_order;
```

### Favorites Table

```sql
-- Columns: user_id, block_id, created_at
-- Primary key: (user_id, block_id)

SELECT b.* FROM favorites f
JOIN blocks b ON b.id = f.block_id
WHERE f.user_id = 'user-uuid';
```

## Storage

Bucket `block-media` stores uploaded files:
- Path pattern: `{block_id}/{uuid}.{ext}`
- Public read access enabled

## Additional Resources

For complete table definitions, constraints, and RLS policies, see `references/schema.md`.
