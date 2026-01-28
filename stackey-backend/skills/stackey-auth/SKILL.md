---
name: stackey-auth
description: Use this skill when users mention "Stackey authentication", "JWT token", "admin access", "user role", "OAuth", "Supabase auth", or when implementing authentication flows for the Stackey backend.
version: 1.0.0
context: fork
---

# Stackey Authentication

Authentication patterns for the StackeyBackend Supabase Edge Functions.

## Authentication Architecture

The backend uses Supabase Auth with JWT tokens. All authentication logic is handled in Edge Functions using a service role key to bypass RLS.

```
┌──────────┐     ┌─────────────────┐     ┌──────────────┐
│  Client  │────▶│  Edge Function  │────▶│   Database   │
│          │     │                 │     │              │
│ JWT Token│     │ getAuthContext()│     │ Service Role │
└──────────┘     │ requireAuth()   │     │ (bypass RLS) │
                 │ requireAdmin()  │     └──────────────┘
                 └─────────────────┘
```

## Authentication Levels

| Level | Requirement | Use Case |
|-------|-------------|----------|
| **Public** | None | Viewing public blocks |
| **User** | Valid JWT | Managing favorites, viewing profile |
| **Admin** | JWT + `role='admin'` | Creating/editing blocks, uploading media |

## Token Usage

Include the JWT token in the Authorization header:

```bash
curl -H "Authorization: Bearer <token>" \
  "http://127.0.0.1:54321/functions/v1/users/me"
```

## User Roles

The `users.role` column determines access level:
- `'user'` - Standard user (default)
- `'admin'` - Full write access to blocks and media

Roles are stored in the `users` table, not in the JWT claims.

## OAuth Providers

Supported providers:
- **Google** - Standard OAuth 2.0
- **Apple** - Sign in with Apple

The `/auth-callback` endpoint handles OAuth redirects.

## Quick Reference

**Check if authenticated:**
```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:54321/functions/v1/users/me"
```

**Admin operations require admin token:**
```bash
# This will fail with 403 if not admin
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "New Block"}' \
  "http://127.0.0.1:54321/functions/v1/blocks"
```

## Additional Resources

For detailed authentication implementation patterns, see `references/auth-patterns.md`.
